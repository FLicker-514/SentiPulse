# SentiPulse 数据使用说明

## 目录结构

```
data/
├── stock/
│   └── stock_daily.csv        # A股日线行情
├── news/
│   ├── news_eastmoney.csv     # 东方财富财经新闻
│   ├── news_cninfo.csv        # 巨潮资讯公司公告
│   └── news_stcn.csv          # 证券时报新闻
└── sentipulse.db              # 建表脚本生成的 SQLite 数据库
```

---

## 一、CSV 文件说明

### 1. `stock/stock_daily.csv` — A股日线行情

10,976 条，覆盖 10 家企业 2025-01-02 ~ 2026-06-05 的日线数据。

| 列名 | 类型 | 说明 |
|------|------|------|
| 股票代码 | TEXT | 如 600519 |
| 企业名称 | TEXT | 如 贵州茅台 |
| 交易日期 | TEXT | YYYY-MM-DD |
| 开盘价 | REAL | |
| 最高价 | REAL | |
| 最低价 | REAL | |
| 收盘价 | REAL | |
| 成交量 | REAL | |
| 成交额 | REAL | |
| 振幅 | REAL | % |
| 涨跌幅 | REAL | % |
| 涨跌额 | REAL | |
| 换手率 | REAL | % |
| 复权类型 | TEXT | qfq / hfq / none |

股票有 3 种复权类型：前复权（qfq）、后复权（hfq）和不复权（none），所以同一日期可能有多条记录。

### 2. `news/news_eastmoney.csv` — 东方财富财经新闻

5,230 篇，覆盖 2025-12 ~ 2026-06。

| 列名 | 类型 | 说明 |
|------|------|------|
| 企业名称 | TEXT | 关联企业 |
| 标题 | TEXT | 新闻标题 |
| URL | TEXT | 原文链接 |
| 发布时间 | TEXT | |
| 来源 | TEXT | 如 证券时报、上海证券报 |
| 正文 | TEXT | 摘要/快讯正文 |

> 注意：东方财富 API 仅返回简略信息，正文多为摘要片段，非完整文章。

### 3. `news/news_cninfo.csv` — 巨潮资讯公司公告

3,417 篇，覆盖 2025-01-07 ~ 2026-06-06。

| 列名 | 类型 | 说明 |
|------|------|------|
| 企业名称 | TEXT | 关联企业 |
| 标题 | TEXT | 公告标题 |
| URL | TEXT | 原文链接 |
| 发布时间 | TEXT | |
| 来源 | TEXT | 固定为"巨潮资讯" |
| 正文 | TEXT | PDF 提取正文（前 10,000 字） |

> 正文通过 PyMuPDF 从 PDF 提取。电子排版 PDF 文本质量好，扫描件 OCR 文本质量较差。

### 4. `news/news_stcn.csv` — 证券时报新闻

1,208 篇，覆盖 2024-08-14 ~ 2026-06-05。

| 列名 | 类型 | 说明 |
|------|------|------|
| 企业名称 | TEXT | 关联企业 |
| 标题 | TEXT | 新闻标题 |
| URL | TEXT | 原文链接 |
| 发布时间 | TEXT | |
| 来源 | TEXT | 如 证券时报、e公司、券商中国、第一财经 等 |
| 摘要 | TEXT | 文章摘要 |
| 正文 | TEXT | 详情页完整正文 |

> 通过 Playwright 浏览器采集，正文从文章详情页抓取，内容完整。

---

## 二、构建 SQLite 数据库

### 环境

依赖 Python 标准库，无需额外安装。在项目根目录下运行：

```bash
uv run python data/build_db.py
```

### 表结构

脚本将创建 4 张表：

| 表名 | 来源 CSV | 说明 |
|------|----------|------|
| `stock_daily` | stock/stock_daily.csv | A股日线行情 |
| `news_eastmoney` | news/news_eastmoney.csv | 东方财富财经新闻 |
| `news_cninfo` | news/news_cninfo.csv | 巨潮资讯公司公告 |
| `news_stcn` | news/news_stcn.csv | 证券时报新闻 |

输出文件：`data/sentipulse.db`

### 查询示例

```sql
-- 查询某只股票的历史行情
SELECT 交易日期, 开盘价, 收盘价, 涨跌幅, 成交量
FROM stock_daily
WHERE 企业名称 = '贵州茅台'
ORDER BY 交易日期;

-- 查询某企业的新闻数量（跨来源）
SELECT 'Eastmoney' AS 来源, COUNT(*) FROM news_eastmoney WHERE 企业名称 = '恒瑞医药'
UNION ALL
SELECT 'Cninfo', COUNT(*) FROM news_cninfo WHERE 企业名称 = '恒瑞医药'
UNION ALL
SELECT 'STCN', COUNT(*) FROM news_stcn WHERE 企业名称 = '恒瑞医药';

-- 按日期范围搜索新闻
SELECT 标题, 发布时间, 来源
FROM news_stcn
WHERE 企业名称 = '海光信息'
  AND 发布时间 >= '2026-01-01'
ORDER BY 发布时间 DESC;
```

## 数据来源与爬取过程

详见 `data_crawler/` 目录下的爬虫代码和 README.md 文件。