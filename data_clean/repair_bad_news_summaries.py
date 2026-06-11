import os
import re
import time
import argparse
import pandas as pd
from tqdm import tqdm
from openai import OpenAI


DEFAULT_CORE_PATH = "output/intermediate/news_core_content.csv"
DEFAULT_CHECKPOINT_PATH = "output/intermediate/news_summary_checkpoint.csv"
DEFAULT_REPAIR_DIR = "output/repair"
DEFAULT_REPAIR_CHECKPOINT = "output/intermediate/news_summary_repair_checkpoint_by_row.csv"
DEFAULT_FINAL_OUTPUT = "output/news_summarized.csv"
DEFAULT_BAD_SAMPLES = "output/repair/bad_news_samples_by_row.csv"
DEFAULT_REEXTRACTED = "output/repair/bad_news_samples_reextracted_by_row.csv"
DEFAULT_REPORT = "output/repair/repair_report_by_row.md"
DEFAULT_BACKUP_OLD_SUMMARY = "output/repair/news_summarized_before_repair_backup.csv"


BAD_SUMMARY_PATTERNS = [
    "模型调用失败",
    "未生成摘要",
    "无法形成完整摘要",
    "无法生成摘要",
    "原文信息不足",
    "信息不足",
    "无法总结",
    "无法提取",
    "无法判断",
    "未提供",
]


def ensure_parent_dir(path: str):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def safe_to_csv(df: pd.DataFrame, path: str, index: bool = False, encoding: str = "utf-8-sig"):
    ensure_parent_dir(path)
    try:
        df.to_csv(path, index=index, encoding=encoding)
        print(f"[输出] {path}")
    except PermissionError:
        base, ext = os.path.splitext(path)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        fallback = f"{base}_{timestamp}{ext}"
        df.to_csv(fallback, index=index, encoding=encoding)
        print(f"[警告] 文件被占用，已改存：{fallback}")


def backup_existing_file(src_path: str, backup_path: str):
    """
    覆盖 news_summarized.csv 前自动备份旧文件。
    如果旧文件不存在，则不备份。
    """
    if not os.path.exists(src_path):
        return

    ensure_parent_dir(backup_path)

    try:
        old_df = pd.read_csv(src_path, dtype=str).fillna("")
        old_df.to_csv(backup_path, index=False, encoding="utf-8-sig")
        print(f"[备份] 覆盖前旧文件已备份到：{backup_path}")
    except PermissionError:
        base, ext = os.path.splitext(backup_path)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        fallback = f"{base}_{timestamp}{ext}"
        old_df = pd.read_csv(src_path, dtype=str).fillna("")
        old_df.to_csv(fallback, index=False, encoding="utf-8-sig")
        print(f"[备份] 默认备份文件被占用，已改存：{fallback}")


def normalize_text(text: str) -> str:
    if pd.isna(text):
        return ""
    text = str(text).replace("\u3000", " ")
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


# ============================================================
# 1. 行号对齐
# ============================================================

def align_by_row_index(core_path: str, checkpoint_path: str) -> pd.DataFrame:
    """
    历史结果修复专用：按行号对齐 news_core_content.csv 和 news_summary_checkpoint.csv。

    为什么按行号：
    - news_core_content.csv 没有 news_id；
    - checkpoint 里的 news_id 可能来自旧脚本，ID 规则不一定一致；
    - 这两个文件是在同一次主流程中按同一新闻顺序生成的，因此行号是当前历史文件最可靠的对齐键。

    安全校验：
    - 两个文件行数必须一致；
    - 若 checkpoint 中存在 企业/日期/来源，则要求它们与 core 文件逐行一致。
    """
    core_df = pd.read_csv(core_path, dtype=str).fillna("")
    ckpt_df = pd.read_csv(checkpoint_path, dtype=str).fillna("")

    if len(core_df) != len(ckpt_df):
        raise ValueError(
            f"两个文件行数不一致，不能安全按行号对齐："
            f"core={len(core_df)}, checkpoint={len(ckpt_df)}"
        )

    for col in ["企业", "日期", "来源"]:
        if col in core_df.columns and col in ckpt_df.columns:
            left = core_df[col].fillna("").astype(str).str.strip()
            right = ckpt_df[col].fillna("").astype(str).str.strip()
            mismatch = left.ne(right)
            if mismatch.any():
                examples = mismatch[mismatch].index[:5].tolist()
                raise ValueError(
                    f"字段 {col} 逐行不一致，不能安全按行号对齐。"
                    f"示例行号：{examples}"
                )

    if "内容" not in ckpt_df.columns:
        raise ValueError("checkpoint 文件缺少“内容”列，无法取得旧摘要。")

    merged = core_df.copy()
    merged["row_index"] = range(len(merged))
    merged["内容"] = ckpt_df["内容"].fillna("").astype(str).values
    merged["align_method"] = "row_index"

    return merged


# ============================================================
# 2. 坏样本检测
# ============================================================

def detect_bad_summary_reason(summary: str) -> list[str]:
    s = normalize_text(summary)
    reasons = []

    if s == "":
        reasons.append("empty_summary")

    if len(s) < 20:
        reasons.append("too_short_summary")

    for p in BAD_SUMMARY_PATTERNS:
        if p in s:
            reasons.append(f"bad_phrase:{p}")

    if re.fullmatch(r"[\u4e00-\u9fa5A-Za-z0-9]{1,6}", s):
        reasons.append("not_a_valid_summary")

    return reasons


def detect_bad_core_reason(row: pd.Series) -> list[str]:
    core = normalize_text(row.get("核心内容", ""))
    title = normalize_text(row.get("标题", ""))
    original = normalize_text(row.get("原始正文", ""))

    reasons = []

    if core == "":
        reasons.append("empty_core")

    if len(core) < 50:
        reasons.append("too_short_core")

    if core == title and len(original) > len(title) + 100:
        reasons.append("title_only_core")

    if len(original) > 1000 and len(core) <= len(title) + 20:
        reasons.append("core_likely_over_removed_by_rule")

    return reasons


def is_good_summary(summary: str) -> bool:
    return len(detect_bad_summary_reason(summary)) == 0


# ============================================================
# 3. 重新抽取 core_content
# ============================================================

def safe_remove_noise(text: str) -> str:
    """
    修复版噪声删除。

    注意：
    不再使用容易吞掉全文的贪婪正则，例如：
    证券代码.*证券简称.*
    """
    text = normalize_text(text)

    replacements = [
        "香港交易及結算所有限公司及香港聯合交易所有限公司對本公告之內容概不負責",
        "香港交易及结算所有限公司及香港联合交易所有限公司对本公告之内容概不负责",
        "本公司董事会及全体董事保证本公告内容不存在任何虚假记载、误导性陈述或者重大遗漏",
        "本公司董事会及全体董事保证本公告内容不存在任何虚假记载",
    ]

    for r in replacements:
        text = text.replace(r, " ")

    text = re.sub(r"[-—]\s*\d+\s*[-—]", " ", text)
    text = re.sub(r"第\s*\d+\s*页", " ", text)
    text = re.sub(r"责任编辑[:：]\S{1,20}", " ", text)
    text = re.sub(r"文章来源[:：]\S{1,40}", " ", text)

    return normalize_text(text)


BASE_KEYWORDS = [
    "公告", "董事会", "股东大会", "议案", "决议", "披露", "报告期",
    "年度报告", "季度报告", "半年度报告", "营收", "收入", "营业收入",
    "净利润", "利润", "亏损", "同比", "增长", "下降", "业务", "订单",
    "合同", "项目", "分红", "派息", "回购", "增持", "减持", "融资",
    "发行", "募集资金", "债券", "可转债", "诉讼", "仲裁", "处罚",
    "监管", "问询", "风险", "违约", "停牌", "复牌", "收购", "出售",
    "投资", "合作", "中标", "签署", "终止", "变更", "任命", "辞职",
]

SPECIAL_MARKERS = [
    "重大事项提示",
    "重要内容提示",
    "主要会计数据和财务指标",
    "管理层讨论与分析",
    "经营情况讨论与分析",
    "利润分配方案",
    "本次向特定对象发行",
    "本次发行",
    "募集资金",
    "发行对象",
    "审议通过",
    "风险提示",
    "会议召开",
    "股东大会",
    "权益分派",
    "回购股份",
    "限制性股票",
    "业绩说明会",
]


def split_units(text: str) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []

    pieces = re.split(r"(?<=[。！？；;])\s*|\n+", text)
    units = []

    for p in pieces:
        p = p.strip()
        if len(p) < 8:
            continue

        if len(p) > 600:
            for i in range(0, len(p), 300):
                chunk = p[i:i + 450].strip()
                if len(chunk) >= 20:
                    units.append(chunk)
        else:
            units.append(p)

    return units


def unit_score(unit: str, idx: int) -> int:
    score = 0

    for kw in BASE_KEYWORDS:
        if kw in unit:
            score += 2

    for marker in SPECIAL_MARKERS:
        if marker in unit:
            score += 4

    if re.search(r"\d", unit):
        score += 1

    if re.search(r"亿元|万元|元|%|同比|增长|下降|年度|季度|月|日", unit):
        score += 2

    if idx <= 8:
        score += 1

    if re.search(r"请填上|委任代表|身份证明文件|表格|签名|地址为|投票", unit):
        score -= 3

    return score


def improved_extract_core_content(title: str, body: str, max_chars: int = 5000) -> str:
    title = normalize_text(title)
    body = safe_remove_noise(body)

    if not body:
        return title[:max_chars]

    selected_parts = []

    for marker in SPECIAL_MARKERS:
        pos = body.find(marker)
        if pos >= 0:
            selected_parts.append(body[pos:pos + 1200])

    units = split_units(body)
    scored = [(u, unit_score(u, i), i) for i, u in enumerate(units)]
    scored = sorted(scored, key=lambda x: (-x[1], x[2]))

    picked = scored[:14]
    picked = sorted(picked, key=lambda x: x[2])
    selected_parts.extend([x[0] for x in picked])

    combined = []
    seen = set()

    for part in selected_parts:
        part = normalize_text(part)
        if not part:
            continue

        key = part[:80]
        if key in seen:
            continue

        seen.add(key)
        combined.append(part)

    if not combined:
        combined = [body[:max_chars]]

    core = title + "\n" + "\n".join(combined)
    return normalize_text(core)[:max_chars]


# ============================================================
# 4. DeepSeek 修复
# ============================================================

REPAIR_SYSTEM_PROMPT = """
你是一个严谨、客观的财经新闻数据修复助手。

你的任务是根据给定新闻的标题和重新抽取的核心内容，生成可用于数据分析的客观摘要。

要求：
1. 只总结原文明确出现的信息，不编造事实。
2. 不输出投资建议。
3. 不预测股价。
4. 不主观判断利好或利空，除非原文明确说明。
5. 优先保留关键主体、事件、时间、金额、比例、业务影响、会议事项、发行事项、分红事项、回购事项等信息。
6. 如果是年度报告、季度报告、募集说明书、法律意见书、股东大会通知、代表委任表格等公告型文件，也要根据标题和核心内容概括“公司披露/发布/拟召开/审议/发行/回购”等事实。
7. 不要因为没有完整财务数据就写“原文信息不足”。只有在标题和核心内容都完全无法判断事项时，才输出“原文信息不足，无法形成完整摘要”。
8. 输出一段中文摘要，长度控制在 80 到 220 字。
""".strip()


def build_repair_prompt(row: pd.Series) -> str:
    return f"""
请修复下面这条财经新闻摘要。

企业：{row.get("企业", "")}
日期：{row.get("日期", "")}
来源：{row.get("来源", "")}
标题：{row.get("标题", "")}

原摘要：
{row.get("内容", "")}

重新抽取的核心内容：
{row.get("修复后核心内容", "")}

请只输出修复后的摘要，不要输出解释。
""".strip()


def init_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "请先设置环境变量 DEEPSEEK_API_KEY。"
            "PowerShell 示例：$env:DEEPSEEK_API_KEY='你的APIKey'"
        )

    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def repair_one(client: OpenAI, row: pd.Series, max_retries: int = 3) -> str:
    prompt = build_repair_prompt(row)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=400,
                stream=False,
            )

            text = response.choices[0].message.content.strip()
            return re.sub(r"\s+", " ", text)

        except Exception as e:
            print(f"[DeepSeek 修复失败] 第 {attempt + 1} 次：{e}")
            time.sleep(2 * (attempt + 1))

    return "模型调用失败，未生成摘要"


def load_repair_checkpoint(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=["row_index", "企业", "日期", "来源", "标题", "URL", "内容"])

    df = pd.read_csv(path, dtype=str).fillna("")
    if "row_index" not in df.columns:
        df["row_index"] = ""

    df["row_index"] = df["row_index"].astype(str)
    df = df.drop_duplicates(subset=["row_index"], keep="last")
    return df


def append_repair_checkpoint(result: dict, path: str):
    ensure_parent_dir(path)
    exists = os.path.exists(path)
    pd.DataFrame([result]).to_csv(
        path,
        mode="a",
        header=not exists,
        index=False,
        encoding="utf-8-sig",
    )


# ============================================================
# 5. 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="按行号对齐并修复坏新闻摘要。")
    parser.add_argument("--core", default=DEFAULT_CORE_PATH)
    parser.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT_PATH)
    parser.add_argument("--repair-checkpoint", default=DEFAULT_REPAIR_CHECKPOINT)
    parser.add_argument("--output-final", default=DEFAULT_FINAL_OUTPUT)
    parser.add_argument("--bad-samples", default=DEFAULT_BAD_SAMPLES)
    parser.add_argument("--bad-reextracted", default=DEFAULT_REEXTRACTED)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--backup-old-summary", default=DEFAULT_BACKUP_OLD_SUMMARY)
    parser.add_argument("--detect-only", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.3)
    parser.add_argument("--max-retries", type=int, default=3)

    args = parser.parse_args()
    os.makedirs(DEFAULT_REPAIR_DIR, exist_ok=True)

    print("========== Step 1: 按行号对齐 core 和 checkpoint ==========")
    merged = align_by_row_index(args.core, args.checkpoint)

    print(f"  对齐方式：row_index")
    print(f"  对齐行数：{len(merged)}")

    print("\n========== Step 2: 检测坏样本 ==========")
    merged["bad_summary_reason"] = merged["内容"].apply(lambda x: ";".join(detect_bad_summary_reason(x)))
    merged["bad_core_reason"] = merged.apply(lambda row: ";".join(detect_bad_core_reason(row)), axis=1)
    merged["need_repair"] = (merged["bad_summary_reason"] != "") | (merged["bad_core_reason"] != "")

    bad_df = merged[merged["need_repair"]].copy()

    print(f"  总样本数：{len(merged)}")
    print(f"  坏样本数：{len(bad_df)}")
    print(f"  坏摘要数：{(merged['bad_summary_reason'] != '').sum()}")
    print(f"  坏 core_content 数：{(merged['bad_core_reason'] != '').sum()}")

    print("\n========== Step 3: 重新抽取坏样本 core_content ==========")
    bad_df["修复后核心内容"] = bad_df.apply(
        lambda row: improved_extract_core_content(
            title=row.get("标题", ""),
            body=row.get("原始正文", ""),
            max_chars=5000,
        ),
        axis=1,
    )

    bad_cols = [
        "row_index", "align_method", "企业", "日期", "来源", "标题", "URL",
        "内容", "bad_summary_reason", "bad_core_reason", "核心内容", "原始正文"
    ]

    bad_re_cols = [
        "row_index", "align_method", "企业", "日期", "来源", "标题", "URL",
        "内容", "bad_summary_reason", "bad_core_reason", "核心内容", "修复后核心内容"
    ]

    safe_to_csv(bad_df[bad_cols], args.bad_samples, index=False)
    safe_to_csv(bad_df[bad_re_cols], args.bad_reextracted, index=False)

    if args.detect_only:
        print("\n已开启 --detect-only，只检测和重抽 core，不调用 DeepSeek。")
        return

    print("\n========== Step 4: 只修复坏样本摘要 ==========")
    client = init_client()

    repair_ckpt = load_repair_checkpoint(args.repair_checkpoint)

    finished_rows = set()
    if not args.force and not repair_ckpt.empty:
        for _, row in repair_ckpt.iterrows():
            if is_good_summary(row.get("内容", "")):
                finished_rows.add(str(row.get("row_index", "")))

    pending = bad_df[~bad_df["row_index"].astype(str).isin(finished_rows)].copy()

    if args.limit is not None:
        pending = pending.head(args.limit).copy()

    print(f"  坏样本总数：{len(bad_df)}")
    print(f"  已修复合格数：{len(finished_rows)}")
    print(f"  本次待修复数：{len(pending)}")
    print(f"  修复断点文件：{args.repair_checkpoint}")

    for _, row in tqdm(pending.iterrows(), total=len(pending), desc="DeepSeek 修复摘要"):
        summary = repair_one(client, row, max_retries=args.max_retries)

        result = {
            "row_index": row.get("row_index", ""),
            "企业": row.get("企业", ""),
            "日期": row.get("日期", ""),
            "来源": row.get("来源", ""),
            "标题": row.get("标题", ""),
            "URL": row.get("URL", ""),
            "原摘要": row.get("内容", ""),
            "bad_summary_reason": row.get("bad_summary_reason", ""),
            "bad_core_reason": row.get("bad_core_reason", ""),
            "修复后核心内容": row.get("修复后核心内容", ""),
            "内容": summary,
        }

        append_repair_checkpoint(result, args.repair_checkpoint)
        time.sleep(args.sleep)

    print("\n========== Step 5: 合并修复结果 ==========")
    repair_ckpt = load_repair_checkpoint(args.repair_checkpoint)
    repair_map = dict(zip(repair_ckpt["row_index"].astype(str), repair_ckpt["内容"].fillna("").astype(str)))

    final = merged.copy()
    replaced = 0

    for idx, row in final.iterrows():
        rid = str(row["row_index"])
        if rid in repair_map and is_good_summary(repair_map[rid]):
            final.at[idx, "内容"] = repair_map[rid]
            replaced += 1

    final["final_bad_summary_reason"] = final["内容"].apply(lambda x: ";".join(detect_bad_summary_reason(x)))
    remaining_bad = final[final["final_bad_summary_reason"] != ""].copy()

    final_output = final[["企业", "日期", "来源", "内容"]].copy()

    # 默认直接覆盖 output/news_summarized.csv。
    # 覆盖前先把旧文件备份到 output/repair/news_summarized_before_repair_backup.csv。
    backup_existing_file(args.output_final, args.backup_old_summary)
    safe_to_csv(final_output, args.output_final, index=False)

    report = []
    report.append("# 新闻摘要修复报告\n")
    report.append(f"- 对齐方式：row_index")
    report.append(f"- 总样本数：{len(final)}")
    report.append(f"- 检测出的坏样本数：{len(bad_df)}")
    report.append(f"- 已替换为合格修复摘要的数量：{replaced}")
    report.append(f"- 修复后仍异常的摘要数量：{len(remaining_bad)}")
    report.append("")
    report.append("说明：本脚本不依赖 news_id。它按行号对齐 news_core_content.csv 和 news_summary_checkpoint.csv。重新抽取 core_content 时，直接使用 news_core_content.csv 中保存的 原始正文 和 标题。")

    ensure_parent_dir(args.report)
    with open(args.report, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"[输出] {args.report}")

    print("\n========== 完成 ==========")
    print(f"最终修复文件：{args.output_final}")
    print(f"仍需检查数量：{len(remaining_bad)}")


if __name__ == "__main__":
    main()
