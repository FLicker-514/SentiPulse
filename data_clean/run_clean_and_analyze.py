import os
import re
import time
import hashlib
import pandas as pd
from tqdm import tqdm
from openai import OpenAI


# ============================================================
# 0. 路径配置
# ============================================================

INPUT_STOCK = "stock_daily.csv"

INPUT_NEWS_FILES = [
    "news_cninfo.csv",
    "news_eastmoney.csv",
    "news_stcn.csv",
]

OUTPUT_DIR = "output"
INTERMEDIATE_DIR = os.path.join(OUTPUT_DIR, "intermediate")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(INTERMEDIATE_DIR, exist_ok=True)

OUTPUT_STOCK_CLEANED = os.path.join(OUTPUT_DIR, "stock_daily_cleaned.csv")
OUTPUT_STOCK_ABNORMAL = os.path.join(INTERMEDIATE_DIR, "stock_abnormal_rows.csv")

OUTPUT_NEWS_CORE = os.path.join(INTERMEDIATE_DIR, "news_core_content.csv")
OUTPUT_NEWS_SUMMARIZED = os.path.join(OUTPUT_DIR, "news_summarized.csv")

# DeepSeek 摘要断点续跑文件。
# 每完成一条新闻摘要，就会写入该文件。
# 如果程序中断，下次运行会读取该文件并跳过已完成记录。
OUTPUT_NEWS_SUMMARY_CHECKPOINT = os.path.join(INTERMEDIATE_DIR, "news_summary_checkpoint.csv")

OUTPUT_REPORT = os.path.join(OUTPUT_DIR, "data_analysis_report.md")
OUTPUT_ANALYSIS_XLSX = os.path.join(INTERMEDIATE_DIR, "analysis_tables.xlsx")


# ============================================================
# 1. 股票数据清洗
# ============================================================

def clean_stock_data(stock_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    清洗股票日频数据。

    清洗后输出字段固定为：
    StockCode, Date, Open, High, Low, Close, Adj Close, Volume
    """
    df = pd.read_csv(stock_path)

    required_cols = [
        "StockCode", "Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"
    ]

    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"股票数据缺少必要字段：{missing_cols}")

    df = df[required_cols].copy()
    df["StockCode"] = df["StockCode"].astype(str).str.strip()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    numeric_cols = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    before_rows = len(df)

    key_cols = ["StockCode", "Date", "Open", "High", "Low", "Close", "Volume"]
    df = df.dropna(subset=key_cols).copy()
    after_dropna_rows = len(df)

    invalid_value_mask = (
        (df["Open"] <= 0) |
        (df["High"] <= 0) |
        (df["Low"] <= 0) |
        (df["Close"] <= 0) |
        (df["Volume"] < 0)
    )

    invalid_price_logic_mask = (
        (df["High"] < df[["Open", "Low", "Close"]].max(axis=1)) |
        (df["Low"] > df[["Open", "High", "Close"]].min(axis=1))
    )

    abnormal_mask = invalid_value_mask | invalid_price_logic_mask

    abnormal_df = df[abnormal_mask].copy()
    cleaned_df = df[~abnormal_mask].copy()

    before_dedup_rows = len(cleaned_df)
    cleaned_df = cleaned_df.drop_duplicates(
        subset=["StockCode", "Date"],
        keep="first"
    )

    cleaned_df = cleaned_df.sort_values(["StockCode", "Date"]).reset_index(drop=True)
    abnormal_df = abnormal_df.sort_values(["StockCode", "Date"]).reset_index(drop=True)

    print("[股票清洗]")
    print(f"  原始行数：{before_rows}")
    print(f"  删除缺失后行数：{after_dropna_rows}")
    print(f"  异常行数：{len(abnormal_df)}")
    print(f"  重复删除行数：{before_dedup_rows - len(cleaned_df)}")
    print(f"  清洗后行数：{len(cleaned_df)}")

    return cleaned_df, abnormal_df


# ============================================================
# 2. 新闻数据读取与统一
# ============================================================

def read_and_merge_news(news_paths: list[str]) -> pd.DataFrame:
    """
    读取并合并多个新闻来源，统一为：
    企业, 日期, 来源, 标题, URL, 原始正文
    """
    all_news = []

    for path in news_paths:
        df = pd.read_csv(path)

        company_col = "企业名称" if "企业名称" in df.columns else "企业"
        date_col = "发布时间" if "发布时间" in df.columns else "日期"

        title_col = "标题" if "标题" in df.columns else None
        source_col = "来源" if "来源" in df.columns else None
        url_col = "URL" if "URL" in df.columns else None
        body_col = "正文" if "正文" in df.columns else None
        summary_col = "摘要" if "摘要" in df.columns else None

        temp = pd.DataFrame()
        temp["企业"] = df[company_col].fillna("").astype(str) if company_col in df.columns else ""
        temp["日期"] = df[date_col] if date_col in df.columns else ""
        temp["来源"] = df[source_col].fillna("").astype(str) if source_col else os.path.basename(path)
        temp["标题"] = df[title_col].fillna("").astype(str) if title_col else ""
        temp["URL"] = df[url_col].fillna("").astype(str) if url_col else ""

        if summary_col and body_col:
            temp["原始正文"] = (
                df[summary_col].fillna("").astype(str)
                + "\n"
                + df[body_col].fillna("").astype(str)
            )
        elif body_col:
            temp["原始正文"] = df[body_col].fillna("").astype(str)
        elif summary_col:
            temp["原始正文"] = df[summary_col].fillna("").astype(str)
        else:
            temp["原始正文"] = ""

        all_news.append(temp)

    news_df = pd.concat(all_news, ignore_index=True)

    news_df["日期"] = pd.to_datetime(
        news_df["日期"],
        errors="coerce",
        format="mixed"
    ).dt.strftime("%Y-%m-%d")

    valid_mask = (
        news_df["企业"].fillna("").astype(str).str.strip().ne("") |
        news_df["标题"].fillna("").astype(str).str.strip().ne("") |
        news_df["原始正文"].fillna("").astype(str).str.strip().ne("")
    )
    news_df = news_df[valid_mask].copy()

    news_df = news_df.drop_duplicates(
        subset=["企业", "日期", "来源", "标题", "URL"],
        keep="first"
    )

    news_df = news_df.reset_index(drop=True)

    print("[新闻读取]")
    print(f"  合并后新闻数量：{len(news_df)}")

    return news_df


# ============================================================
# 3. 非智能体方法定位新闻核心内容
# ============================================================

NOISE_PATTERNS = [
    r"香港交易及结算所有限公司.*?概不负责",
    r"香港聯合交易所有限公司.*?概不負責",
    r"本公司董事会及全体董事.*?承担法律责任",
    r"本公告内容不存在任何虚假记载.*?法律责任",
    r"证券代码[:：].*?证券简称[:：].*",
    r"公告编号[:：].*",
    r"第\s*\d+\s*页",
    r"[-—]\s*\d+\s*[-—]",
    r"责任编辑[:：].*",
    r"文章来源[:：].*",
    r"原标题[:：].*",
    r"免责声明[:：].*",
]

CORE_KEYWORDS = [
    "公告", "董事会", "股东大会", "议案", "决议", "披露", "报告期",
    "年度报告", "季度报告", "营收", "收入", "净利润", "利润", "亏损",
    "同比", "增长", "下降", "业务", "订单", "合同", "项目",
    "分红", "派息", "回购", "增持", "减持", "融资", "发行",
    "债券", "可转债", "诉讼", "仲裁", "处罚", "监管", "问询",
    "风险", "违约", "停牌", "复牌", "收购", "出售", "投资",
    "合作", "中标", "签署", "终止", "变更", "任命", "辞职",
]

STRUCTURE_MARKERS = [
    "重要内容提示",
    "一、",
    "二、",
    "三、",
    "本次公告",
    "本次交易",
    "本次会议",
    "本次回购",
    "本次投资",
    "风险提示",
]


def normalize_text(text: str) -> str:
    if pd.isna(text):
        return ""

    text = str(text)
    text = text.replace("\u3000", " ")
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def remove_noise(text: str) -> str:
    text = normalize_text(text)

    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.S)

    return normalize_text(text)


def split_paragraphs(text: str) -> list[str]:
    text = normalize_text(text)
    paragraphs = re.split(r"\n+", text)

    cleaned = []
    for p in paragraphs:
        p = p.strip()
        p = re.sub(r"\s+", " ", p)

        if len(p) < 10:
            continue

        cleaned.append(p)

    return cleaned


def score_paragraph(paragraph: str) -> int:
    score = 0

    for kw in CORE_KEYWORDS:
        if kw in paragraph:
            score += 2

    for marker in STRUCTURE_MARKERS:
        if marker in paragraph:
            score += 3

    if re.search(r"\d", paragraph):
        score += 1

    if re.search(r"亿元|万元|元|%|同比|年度|季度|月|日", paragraph):
        score += 2

    if len(paragraph) > 1500:
        score -= 1

    return score


def extract_core_content(title: str, body: str, max_chars: int = 4000) -> str:
    """
    使用规则方法提取新闻核心内容。
    该步骤不调用大模型。
    """
    title = normalize_text(title)
    body = remove_noise(body)

    if not body:
        return title[:max_chars]

    paragraphs = split_paragraphs(body)

    if not paragraphs:
        return (title + "\n" + body)[:max_chars].strip()

    structure_start_idx = None
    for i, p in enumerate(paragraphs):
        if any(marker in p for marker in STRUCTURE_MARKERS):
            structure_start_idx = i
            break

    if structure_start_idx is not None:
        selected = paragraphs[structure_start_idx:structure_start_idx + 8]
    else:
        scored = [(p, score_paragraph(p), i) for i, p in enumerate(paragraphs)]

        adjusted = []
        for p, s, i in scored:
            if i <= 5:
                s += 1
            adjusted.append((p, s, i))

        adjusted = sorted(adjusted, key=lambda x: (-x[1], x[2]))

        selected = adjusted[:6]
        selected = sorted(selected, key=lambda x: x[2])
        selected = [x[0] for x in selected]

    core_content = title + "\n" + "\n".join(selected)
    return core_content[:max_chars].strip()


def build_news_core_content(news_df: pd.DataFrame) -> pd.DataFrame:
    df = news_df.copy()

    df["核心内容"] = df.apply(
        lambda row: extract_core_content(
            title=row.get("标题", ""),
            body=row.get("原始正文", ""),
            max_chars=4000,
        ),
        axis=1,
    )

    return df


# ============================================================
# 4. DeepSeek 总结新闻：支持断点续跑
# ============================================================

SYSTEM_PROMPT = """
你是一个严谨、客观的财经新闻清洗助手。

你的任务是根据给定的新闻核心内容，总结该新闻的主要事实。

要求：
1. 只总结原文中明确出现的信息。
2. 不添加投资建议。
3. 不预测股价。
4. 不判断利好或利空，除非原文明确说明。
5. 不使用夸张、营销化、情绪化表达。
6. 保留关键主体、事件、时间、金额、比例、业务影响等信息。
7. 如果原文信息不足，只写“原文信息不足，无法形成完整摘要”。
8. 输出一段中文摘要，长度控制在 80~180 字。
""".strip()


def build_user_prompt(row: pd.Series) -> str:
    return f"""
请对以下财经新闻核心内容进行客观总结。

企业：{row.get("企业", "")}
日期：{row.get("日期", "")}
来源：{row.get("来源", "")}
标题：{row.get("标题", "")}

核心内容：
{row.get("核心内容", "")}

请只输出总结后的内容，不要输出解释。
""".strip()


def init_deepseek_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "请先设置环境变量 DEEPSEEK_API_KEY。"
            "例如：export DEEPSEEK_API_KEY='你的APIKey'"
        )

    return OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )


def summarize_one_news(client: OpenAI, row: pd.Series, max_retries: int = 3) -> str:
    user_prompt = build_user_prompt(row)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=300,
                stream=False,
            )

            summary = response.choices[0].message.content.strip()
            summary = re.sub(r"\s+", " ", summary)
            return summary

        except Exception as e:
            print(f"[DeepSeek 调用失败] 第 {attempt + 1} 次：{e}")
            time.sleep(2 * (attempt + 1))

    return "模型调用失败，未生成摘要"


def build_news_id(row: pd.Series) -> str:
    """
    为每条新闻构造稳定 ID，用于断点续跑。

    不能使用 Python 内置 hash()，因为不同进程 hash 随机化，重启后可能变化。
    这里使用 md5，保证下次运行时同一条新闻得到同一个 news_id。
    """
    fields = [
        str(row.get("企业", "")),
        str(row.get("日期", "")),
        str(row.get("来源", "")),
        str(row.get("标题", "")),
        str(row.get("URL", "")),
    ]
    raw_id = "||".join(fields)
    return hashlib.md5(raw_id.encode("utf-8")).hexdigest()


def load_summary_checkpoint(checkpoint_path: str) -> pd.DataFrame:
    """
    读取已经完成的摘要结果。
    如果断点文件不存在，返回空表。
    """
    if not os.path.exists(checkpoint_path):
        return pd.DataFrame(columns=["news_id", "企业", "日期", "来源", "内容"])

    checkpoint_df = pd.read_csv(checkpoint_path, dtype={"news_id": str})

    required_cols = ["news_id", "企业", "日期", "来源", "内容"]
    for col in required_cols:
        if col not in checkpoint_df.columns:
            checkpoint_df[col] = ""

    checkpoint_df = checkpoint_df[required_cols].copy()

    # 如果同一 news_id 多次写入，保留最后一次。
    checkpoint_df = checkpoint_df.drop_duplicates(subset=["news_id"], keep="last")

    return checkpoint_df


def append_summary_checkpoint(row_dict: dict, checkpoint_path: str):
    """
    将单条摘要结果追加写入断点文件。
    每完成一条就落盘，尽量避免中断后丢失进度。
    """
    one_row_df = pd.DataFrame([row_dict])
    file_exists = os.path.exists(checkpoint_path)

    one_row_df.to_csv(
        checkpoint_path,
        mode="a",
        header=not file_exists,
        index=False,
        encoding="utf-8-sig",
    )


def summarize_news_with_deepseek(
    news_core_df: pd.DataFrame,
    checkpoint_path: str = OUTPUT_NEWS_SUMMARY_CHECKPOINT,
) -> pd.DataFrame:
    """
    批量调用 DeepSeek 总结新闻，支持断点续跑。

    断点续跑逻辑：
    1. 为每条新闻生成 news_id。
    2. 启动时读取 checkpoint 文件。
    3. 如果 news_id 已经在 checkpoint 中，则跳过。
    4. 对未完成新闻调用 DeepSeek。
    5. 每完成一条立即追加写入 checkpoint。
    6. 全部完成后，从 checkpoint 整理生成最终 news_summarized.csv。
    """
    client = init_deepseek_client()

    df = news_core_df.copy()
    df["news_id"] = df.apply(build_news_id, axis=1)

    checkpoint_df = load_summary_checkpoint(checkpoint_path)
    finished_ids = set(checkpoint_df["news_id"].astype(str).tolist())

    pending_df = df[~df["news_id"].astype(str).isin(finished_ids)].copy()

    print("[DeepSeek 断点续跑]")
    print(f"  新闻总数：{len(df)}")
    print(f"  已完成：{len(finished_ids)}")
    print(f"  待处理：{len(pending_df)}")
    print(f"  断点文件：{checkpoint_path}")

    for _, row in tqdm(pending_df.iterrows(), total=len(pending_df), desc="DeepSeek 新闻总结"):
        summary = summarize_one_news(client, row)

        result = {
            "news_id": str(row["news_id"]),
            "企业": row.get("企业", ""),
            "日期": row.get("日期", ""),
            "来源": row.get("来源", ""),
            "内容": summary,
        }

        append_summary_checkpoint(result, checkpoint_path)

        # 控制请求频率，避免触发限流。
        time.sleep(0.3)

    final_checkpoint_df = load_summary_checkpoint(checkpoint_path)

    final_df = df[["news_id", "企业", "日期", "来源"]].merge(
        final_checkpoint_df[["news_id", "内容"]],
        on="news_id",
        how="left",
    )

    missing_count = final_df["内容"].isna().sum()
    if missing_count > 0:
        print(f"[警告] 仍有 {missing_count} 条新闻没有摘要。最终文件中会保留空内容。")

    output_df = final_df[["企业", "日期", "来源", "内容"]].copy()

    return output_df


# ============================================================
# 5. 股票数据分析
# ============================================================

def analyze_stock_data(stock_df: pd.DataFrame) -> dict:
    df = stock_df.copy()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    numeric_cols = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    basic_info = {
        "股票数据总行数": len(df),
        "股票代码数量": df["StockCode"].nunique(),
        "开始日期": df["Date"].min(),
        "结束日期": df["Date"].max(),
        "缺失值统计": df.isna().sum().to_dict(),
    }

    stock_by_company = df.groupby("StockCode").agg(
        start_date=("Date", "min"),
        end_date=("Date", "max"),
        record_count=("Date", "count"),
        mean_close=("Close", "mean"),
        std_close=("Close", "std"),
        min_close=("Close", "min"),
        max_close=("Close", "max"),
        mean_volume=("Volume", "mean"),
        std_volume=("Volume", "std"),
    ).reset_index()

    df["Month"] = df["Date"].dt.to_period("M").astype(str)

    stock_by_month = df.groupby("Month").agg(
        record_count=("Date", "count"),
        stock_count=("StockCode", "nunique"),
        mean_close=("Close", "mean"),
        mean_volume=("Volume", "mean"),
    ).reset_index()

    df = df.sort_values(["StockCode", "Date"]).reset_index(drop=True)
    df["daily_return"] = df.groupby("StockCode")["Close"].pct_change()

    volatility = df.groupby("StockCode").agg(
        mean_daily_return=("daily_return", "mean"),
        std_daily_return=("daily_return", "std"),
        max_daily_return=("daily_return", "max"),
        min_daily_return=("daily_return", "min"),
    ).reset_index()

    abnormal_return = df[df["daily_return"].abs() > 0.10].copy()

    volume_abnormal_list = []
    for stock_code, group in df.groupby("StockCode"):
        q1 = group["Volume"].quantile(0.25)
        q3 = group["Volume"].quantile(0.75)
        iqr = q3 - q1
        upper = q3 + 3 * iqr

        temp = group[group["Volume"] > upper].copy()
        if not temp.empty:
            temp["volume_iqr_upper"] = upper
            volume_abnormal_list.append(temp)

    if volume_abnormal_list:
        abnormal_volume = pd.concat(volume_abnormal_list, ignore_index=True)
    else:
        abnormal_volume = pd.DataFrame(columns=list(df.columns) + ["volume_iqr_upper"])

    return {
        "basic_info": basic_info,
        "stock_by_company": stock_by_company,
        "stock_by_month": stock_by_month,
        "volatility": volatility,
        "abnormal_return": abnormal_return,
        "abnormal_volume": abnormal_volume,
    }


# ============================================================
# 6. 新闻数据分析
# ============================================================

def analyze_news_data(news_df: pd.DataFrame) -> dict:
    df = news_df.copy()

    df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
    df["内容"] = df["内容"].fillna("").astype(str)
    df["内容长度"] = df["内容"].str.len()
    df["Month"] = df["日期"].dt.to_period("M").astype(str)

    basic_info = {
        "新闻总数": len(df),
        "企业数量": df["企业"].nunique(),
        "来源数量": df["来源"].nunique(),
        "开始日期": df["日期"].min(),
        "结束日期": df["日期"].max(),
        "内容长度均值": df["内容长度"].mean(),
        "内容长度中位数": df["内容长度"].median(),
        "内容长度最大值": df["内容长度"].max(),
        "内容长度最小值": df["内容长度"].min(),
        "缺失值统计": df.isna().sum().to_dict(),
    }

    news_by_company = df.groupby("企业").agg(
        record_count=("内容", "count"),
        start_date=("日期", "min"),
        end_date=("日期", "max"),
        mean_content_length=("内容长度", "mean"),
    ).reset_index()

    news_by_source = df.groupby("来源").agg(
        record_count=("内容", "count"),
        mean_content_length=("内容长度", "mean"),
    ).reset_index()

    news_by_month = df.groupby("Month").agg(
        record_count=("内容", "count"),
        company_count=("企业", "nunique"),
    ).reset_index()

    abnormal_short_news = df[df["内容长度"] < 20].copy()

    return {
        "basic_info": basic_info,
        "news_by_company": news_by_company,
        "news_by_source": news_by_source,
        "news_by_month": news_by_month,
        "abnormal_short_news": abnormal_short_news,
    }


# ============================================================
# 7. Markdown 报告生成
# ============================================================

def format_date(value) -> str:
    if pd.isna(value):
        return "NA"
    return str(value)[:10]


def generate_report(
    stock_analysis: dict,
    news_analysis: dict,
    stock_abnormal_rows: pd.DataFrame,
    output_path: str,
):
    stock_info = stock_analysis["basic_info"]
    news_info = news_analysis["basic_info"]

    report = []

    report.append("# 数据清洗与数据分析报告\n")

    report.append("## 1. 数据处理目标\n")
    report.append(
        "本项目对股票日频数据与财经新闻数据进行清洗和分析。"
        "股票数据保留股票代码和日频行情字段，新闻数据采用“规则抽取核心内容 + DeepSeek 客观摘要”的两阶段方法处理。"
    )
    report.append("")

    report.append("## 2. 股票数据清洗规则\n")
    report.append(
        "清洗后的股票数据字段为：StockCode, Date, Open, High, Low, Close, Adj Close, Volume。"
        "其中 StockCode 用于标识股票；Open、High、Low、Close 为不复权价格；Adj Close 保留为参考字段；Volume 为成交量。"
    )
    report.append("")
    report.append("主要清洗步骤包括：日期格式统一、数值字段类型转换、关键字段缺失值删除、价格与成交量异常检查、High/Low 逻辑一致性检查、同一股票同一日期去重、按股票代码和日期排序。")
    report.append("")

    report.append("## 3. 股票数据规模分析\n")
    report.append(f"- 股票数据总行数：{stock_info['股票数据总行数']}")
    report.append(f"- 股票代码数量：{stock_info['股票代码数量']}")
    report.append(f"- 日期范围：{format_date(stock_info['开始日期'])} 至 {format_date(stock_info['结束日期'])}")
    report.append("")

    report.append("### 3.1 按股票代码统计\n")
    report.append(stock_analysis["stock_by_company"].to_markdown(index=False))
    report.append("")

    report.append("### 3.2 按月份统计\n")
    report.append(stock_analysis["stock_by_month"].to_markdown(index=False))
    report.append("")

    report.append("## 4. 股票波动与异常分析\n")
    report.append("### 4.1 日收益率波动\n")
    report.append(stock_analysis["volatility"].to_markdown(index=False))
    report.append("")
    report.append("### 4.2 异常记录统计\n")
    report.append(f"- 价格、成交量或 High/Low 逻辑异常行数：{len(stock_abnormal_rows)}")
    report.append(f"- 单日收益率绝对值超过 10% 的记录数：{len(stock_analysis['abnormal_return'])}")
    report.append(f"- 基于 IQR 方法识别出的成交量异常记录数：{len(stock_analysis['abnormal_volume'])}")
    report.append("")

    report.append("## 5. 新闻数据清洗规则\n")
    report.append(
        "新闻数据先合并 cninfo、eastmoney、stcn 三个来源，统一字段为企业、日期、来源、标题、URL 和原始正文。"
        "随后使用规则方法删除免责声明、页眉页脚、版权信息、文章来源等噪声内容，并根据关键词、结构化标题和段落位置抽取核心内容。"
        "最后将核心内容输入 DeepSeek，生成客观摘要。"
    )
    report.append("")

    report.append("## 6. 新闻数据规模分析\n")
    report.append(f"- 新闻总数：{news_info['新闻总数']}")
    report.append(f"- 企业数量：{news_info['企业数量']}")
    report.append(f"- 来源数量：{news_info['来源数量']}")
    report.append(f"- 日期范围：{format_date(news_info['开始日期'])} 至 {format_date(news_info['结束日期'])}")
    report.append(f"- 摘要内容长度均值：{news_info['内容长度均值']:.2f}")
    report.append(f"- 摘要内容长度中位数：{news_info['内容长度中位数']:.2f}")
    report.append("")

    report.append("### 6.1 按企业统计新闻数量\n")
    report.append(news_analysis["news_by_company"].to_markdown(index=False))
    report.append("")

    report.append("### 6.2 按来源统计新闻数量\n")
    report.append(news_analysis["news_by_source"].to_markdown(index=False))
    report.append("")

    report.append("### 6.3 按月份统计新闻数量\n")
    report.append(news_analysis["news_by_month"].to_markdown(index=False))
    report.append("")

    report.append("## 7. 新闻异常数据检查\n")
    report.append(f"- 摘要内容长度少于 20 字的新闻数量：{len(news_analysis['abnormal_short_news'])}")
    report.append("")

    report.append("## 8. 方法总结\n")
    report.append(
        "本流程强调可复现性。股票数据清洗采用确定性规则，保证字段规范、日期规范、数值有效和股票标识可追溯。"
        "新闻数据没有直接将全文交给大模型，而是先用非智能体规则定位核心内容，再由 DeepSeek 摘要。"
        "这样既能降低模型输入噪声，也能减少摘要偏移，使最终新闻数据更适合后续统计分析和实验报告撰写。"
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))


# ============================================================
# 8. 保存分析表
# ============================================================

def save_analysis_tables(
    stock_analysis: dict,
    news_analysis: dict,
    stock_abnormal_rows: pd.DataFrame,
    output_path: str,
):
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        stock_analysis["stock_by_company"].to_excel(writer, sheet_name="stock_by_company", index=False)
        stock_analysis["stock_by_month"].to_excel(writer, sheet_name="stock_by_month", index=False)
        stock_analysis["volatility"].to_excel(writer, sheet_name="stock_volatility", index=False)
        stock_analysis["abnormal_return"].to_excel(writer, sheet_name="stock_abnormal_return", index=False)
        stock_analysis["abnormal_volume"].to_excel(writer, sheet_name="stock_abnormal_volume", index=False)
        stock_abnormal_rows.to_excel(writer, sheet_name="stock_abnormal_cleaning", index=False)

        news_analysis["news_by_company"].to_excel(writer, sheet_name="news_by_company", index=False)
        news_analysis["news_by_source"].to_excel(writer, sheet_name="news_by_source", index=False)
        news_analysis["news_by_month"].to_excel(writer, sheet_name="news_by_month", index=False)
        news_analysis["abnormal_short_news"].to_excel(writer, sheet_name="news_abnormal_short", index=False)


# ============================================================
# 9. 主流程
# ============================================================

def main():
    print("========== Step 1: 清洗股票数据 ==========")
    stock_cleaned, stock_abnormal = clean_stock_data(INPUT_STOCK)

    stock_cleaned.to_csv(OUTPUT_STOCK_CLEANED, index=False, encoding="utf-8-sig")
    stock_abnormal.to_csv(OUTPUT_STOCK_ABNORMAL, index=False, encoding="utf-8-sig")

    print(f"[输出] {OUTPUT_STOCK_CLEANED}")
    print(f"[输出] {OUTPUT_STOCK_ABNORMAL}")

    print("\n========== Step 2: 读取并合并新闻数据 ==========")
    news_raw = read_and_merge_news(INPUT_NEWS_FILES)

    print("\n========== Step 3: 非智能体方法抽取新闻核心内容 ==========")
    news_core = build_news_core_content(news_raw)
    news_core.to_csv(OUTPUT_NEWS_CORE, index=False, encoding="utf-8-sig")
    print(f"[输出] {OUTPUT_NEWS_CORE}")

    print("\n========== Step 4: DeepSeek 总结新闻 ==========")
    news_summarized = summarize_news_with_deepseek(
        news_core,
        checkpoint_path=OUTPUT_NEWS_SUMMARY_CHECKPOINT,
    )
    news_summarized.to_csv(OUTPUT_NEWS_SUMMARIZED, index=False, encoding="utf-8-sig")
    print(f"[输出] {OUTPUT_NEWS_SUMMARIZED}")
    print(f"[断点文件] {OUTPUT_NEWS_SUMMARY_CHECKPOINT}")

    print("\n========== Step 5: 数据分析 ==========")
    stock_analysis = analyze_stock_data(stock_cleaned)
    news_analysis = analyze_news_data(news_summarized)

    print("\n========== Step 6: 生成 Markdown 报告 ==========")
    generate_report(
        stock_analysis=stock_analysis,
        news_analysis=news_analysis,
        stock_abnormal_rows=stock_abnormal,
        output_path=OUTPUT_REPORT,
    )
    print(f"[输出] {OUTPUT_REPORT}")

    print("\n========== Step 7: 保存 Excel 分析表 ==========")
    save_analysis_tables(
        stock_analysis=stock_analysis,
        news_analysis=news_analysis,
        stock_abnormal_rows=stock_abnormal,
        output_path=OUTPUT_ANALYSIS_XLSX,
    )
    print(f"[输出] {OUTPUT_ANALYSIS_XLSX}")

    print("\n全部处理完成。")


if __name__ == "__main__":
    main()
