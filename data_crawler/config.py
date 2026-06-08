"""
SentiPulse 数据采集配置
"""

# ============================================================
# 目标企业列表 (名称 -> A股代码)
# ============================================================
STOCKS: dict[str, str] = {
    "交通银行": "601328",
    "保利发展": "600048",
    "国电南瑞": "600406",
    "工商银行": "601398",
    "恒瑞医药": "600276",
    "海光信息": "688041",
    "海天味业": "603288",
    "海尔智家": "600690",
    "贵州茅台": "600519",
    "金山办公": "688111",
}

# ============================================================
# 数据时间范围
# ============================================================
START_DATE = "2025-01-01"
END_DATE = "2026-06-06"

# AKShare 日期格式 (YYYYMMDD)
START_DATE_AK = "20250101"
END_DATE_AK = "20260606"

# ============================================================
# 请求控制
# ============================================================
STOCK_DELAY_MIN = 0.8   # 股票数据请求最小间隔(秒)
STOCK_DELAY_MAX = 1.5   # 股票数据请求最大间隔(秒)
NEWS_DELAY_MIN = 2.0    # 新闻数据请求最小间隔(秒)
NEWS_DELAY_MAX = 4.0    # 新闻数据请求最大间隔(秒)

REQUEST_TIMEOUT = 30    # 请求超时(秒)
MAX_RETRIES = 3         # 最大重试次数
RETRY_BACKOFF = 5       # 重试退避基础时间(秒)

# ============================================================
# 新闻搜索配置
# ============================================================
# 每个企业的搜索关键词: 公司名 + 股票代码
NEWS_SEARCH_TYPES = ["all", "news"]  # search_type 参数
NEWS_MAX_PAGES = 5     # 每个搜索最多爬取页数

# ============================================================
# 存储配置
# ============================================================
DB_DIR = "data"
DB_NAME = "sentipulse.db"
DB_PATH = f"{DB_DIR}/{DB_NAME}"

# ============================================================
# 日志配置
# ============================================================
LOG_DIR = "logs"
LOG_LEVEL = "INFO"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 单个日志文件最大 10MB
LOG_BACKUP_COUNT = 5              # 保留最近 5 个日志文件

# ============================================================
# HTTP 请求头
# ============================================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

STCN_BASE_URL = "https://www.stcn.com"
STCN_SEARCH_URL = "https://www.stcn.com/article/search.html"
STCN_SEARCH_DATA_URL = "https://www.stcn.com/article/search_data.html"
STCN_KX_LIST_URL = "https://www.stcn.com/article/list.html"
STCN_DETAIL_URL = "https://www.stcn.com/article/detail/{article_id}.html"
