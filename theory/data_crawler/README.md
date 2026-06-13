# （1）数据爬取

代码来源：**LightQuant** `dataset_construction/`，已适配 SentiPulse。

| 文件 | 作用 |
|------|------|
| `news_scraper.py` | 证券时报 stcn.com：抓链接 + 正文 |
| `news_export.py` | JSON → `data/processed/CSMD50/news/<股票>/<日期>.csv` |
| `stock_registry.py` | 股票中文名 ↔ `sh.600519` 代码表 |
| `price_data_collection.py` | baostock 日线（未改路径，需自行调整） |

## 环境准备

```bash
pip install beautifulsoup4 selenium webdriver-manager
```

**GPU 服务器上 `which google-chrome chromedriver` 为空时，必须先装浏览器：**

```bash
# Conda（推荐，无需 root）
conda install -c conda-forge chromium chromedriver -y
export CHROME_BIN=$(which chromium)
export CHROMEDRIVER_PATH=$(which chromedriver)

# 验证
$CHROME_BIN --version
$CHROMEDRIVER_PATH --version
```

然后爬取：

```bash
python run.py crawl-news --symbols 贵州茅台 --ticker sh.600519 --max-articles 15 -o ./data/crawl_out
```

或显式传路径：

```bash
python run.py crawl-news --symbols 贵州茅台 --ticker sh.600519 \
  --chrome-binary $CONDA_PREFIX/bin/chromium \
  --chromedriver $CONDA_PREFIX/bin/chromedriver \
  -o ./data/crawl_out
```

**Mac 本地**（需已安装 [Google Chrome](https://www.google.com/chrome/)）：

```bash
brew install chromedriver
python run.py crawl-news --symbols 贵州茅台 --ticker sh.600519 \
  --chrome-binary "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --chromedriver "$(which chromedriver)" \
  --max-articles 5 -o ./data/crawl_out
```

若 `webdriver-manager` 报 offline，务必 `brew install chromedriver` 并用 `--chromedriver` 指定路径。

**报错 `chromedriver unexpectedly exited. Status code was: -9`（Mac）：**

```bash
xattr -d com.apple.quarantine "$(which chromedriver)"
chromedriver --version    # 必须能输出版本，不能立刻退出
brew upgrade chromedriver
```

Chrome 与 chromedriver **主版本号需一致**（如 Chrome 131 → chromedriver 131）。

**无法在服务器装浏览器时**：在本地电脑跑 `crawl-news`，把 `data/crawl_out` 拷到服务器；或继续用 `setup-data` 从 LightQuant 复制已有新闻。

股票代码表（任选其一）：

- 复制 `LightQuant/llm_factor/CSMD50.csv` → `theory/data_crawler/CSMD50.csv`
- 同级保留 `../LightQuant/llm_factor/CSMD50.csv`（自动读取）
- 已有 `data/processed/CSMD50/news/<股票>/*.csv` 且含 `ticker` 列（自动推断）
- 命令行手动指定：`--ticker sh.600519`

## 试跑（推荐先单只股票、少量文章）

```bash
cd SentiPulse

# 指定输出目录（推荐试跑时用独立文件夹）
python run.py crawl-news --symbols 贵州茅台 --max-articles 15 -o ./data/crawl_out

# 默认目录：JSON 在 theory/data_crawler/_cache/，CSV 在 data/processed/CSMD50/news/
python run.py crawl-news --symbols 贵州茅台 --max-articles 15 --max-scroll 10

# 调试：弹出浏览器窗口
python run.py crawl-news --symbols 贵州茅台 --max-articles 5 --no-headless

# 只抓搜索页链接，不抓正文
python run.py crawl-news --symbols 贵州茅台 --links-only
```

**未指定 `-o` 时：**

| 类型 | 路径 |
|------|------|
| 链接 JSON | `theory/data_crawler/_cache/news_link/` |
| 正文 JSON | `theory/data_crawler/_cache/news_raw/` |
| 按日 CSV | `data/processed/CSMD50/news/<股票>/` |

**指定 `-o /path/to/out` 时：**

```
/path/to/out/
├── news_link/600519.json
├── news_raw/600519.json
└── news/贵州茅台/2024-12-16.csv
```

## 接入流水线

```bash
python run.py crawl-news --symbols 贵州茅台
python run.py setup-data --rebuild
python run.py build-sentiment --symbols 贵州茅台 --force
```

## 说明

- 网站结构变更可能导致解析失败，需检查 `detail-content` / `detail-title` 等 class。
- 爬取频率过高可能被封，试跑请用小 `--max-articles`。
- 服务器无图形界面时请用默认 headless；失败可试 `--no-headless` 在本地调试。
