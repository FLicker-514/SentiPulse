# 股票与新闻数据清洗、摘要和分析流程说明

## 1. 项目目标

本项目用于对股票日频行情数据和财经新闻数据进行清洗、摘要和统计分析，最终形成可用于实验报告的数据产出。

项目包含三类主要任务：

1. 股票数据清洗  
   将原始股票日频数据清洗为结构规范、字段完整、可追溯到股票代码的数据表。

2. 新闻数据清洗与摘要  
   对多个来源的新闻数据进行合并和统一。先用非智能体规则方法定位每条新闻的核心内容，再调用 DeepSeek 对核心内容进行客观摘要。

3. 数据分析  
   从数据规模、时间分布、公司分布、数据波动和异常数据等角度分析股票和新闻数据。

---

## 2. 输入文件

脚本默认读取当前目录下的以下文件：

```text
stock_daily.csv
news_cninfo.csv
news_eastmoney.csv
news_stcn.csv
```

### 2.1 股票数据输入

`stock_daily.csv` 至少应包含以下字段：

```text
StockCode, Date, Open, High, Low, Close, Adj Close, Volume
```

字段含义如下：

| 字段 | 含义 |
|---|---|
| StockCode | 股票代码，用于标识不同股票 |
| Date | 交易日期 |
| Open | 开盘价，不复权价格 |
| High | 最高价，不复权价格 |
| Low | 最低价，不复权价格 |
| Close | 收盘价，不复权价格 |
| Adj Close | 复权收盘价，保留为参考字段 |
| Volume | 成交量 |

### 2.2 新闻数据输入

新闻数据包括三个来源：

```text
news_cninfo.csv
news_eastmoney.csv
news_stcn.csv
```

脚本会兼容以下字段：

| 原始字段 | 统一后字段 |
|---|---|
| 企业名称 | 企业 |
| 发布时间 | 日期 |
| 来源 | 来源 |
| 标题 | 标题 |
| URL | URL |
| 摘要 | 原始正文的一部分 |
| 正文 | 原始正文 |

对于 STCN 数据，如果同时存在 `摘要` 和 `正文`，脚本会将二者合并为原始正文。

---

## 3. 输出文件

脚本运行后会生成 `output/` 文件夹。结构如下：

```text
output/
├── stock_daily_cleaned.csv
├── news_summarized.csv
├── data_analysis_report.md
└── intermediate/
    ├── stock_abnormal_rows.csv
    ├── news_core_content.csv
    └── analysis_tables.xlsx
```

### 3.1 `stock_daily_cleaned.csv`

清洗后的股票数据，字段固定为：

```text
StockCode,Date,Open,High,Low,Close,Adj Close,Volume
```

该文件保留 `StockCode`，因此后续仍然可以区分每一条行情记录属于哪只股票。

### 3.2 `news_summarized.csv`

经过 DeepSeek 摘要后的新闻数据，字段固定为：

```text
企业,日期,来源,内容
```

其中 `内容` 是 DeepSeek 根据新闻核心内容生成的客观摘要，不是原始全文。

### 3.3 `data_analysis_report.md`

Markdown 格式的数据分析报告，包含：

1. 数据处理目标
2. 股票数据清洗规则
3. 股票数据规模分析
4. 股票波动与异常分析
5. 新闻数据清洗规则
6. 新闻数据规模分析
7. 新闻异常数据检查
8. 方法总结

### 3.4 `intermediate/stock_abnormal_rows.csv`

股票清洗过程中识别出的异常行。异常包括：

1. 开盘价、最高价、最低价或收盘价小于等于 0
2. 成交量小于 0
3. `High < max(Open, Low, Close)`
4. `Low > min(Open, High, Close)`

### 3.5 `intermediate/news_core_content.csv`

规则方法抽取出的新闻核心内容。该文件用于检查输入给 DeepSeek 的内容是否合理。

主要字段包括：

```text
企业,日期,来源,标题,URL,原始正文,核心内容
```

### 3.6 `intermediate/analysis_tables.xlsx`

Excel 格式的中间分析表，包括股票和新闻的统计结果。

包含工作表：

| 工作表 | 内容 |
|---|---|
| stock_by_company | 按股票代码统计 |
| stock_by_month | 按月份统计股票数据 |
| stock_volatility | 按股票代码统计日收益率波动 |
| stock_abnormal_return | 单日收益率绝对值超过 10% 的记录 |
| stock_abnormal_volume | 基于 IQR 方法识别的成交量异常记录 |
| stock_abnormal_cleaning | 股票清洗阶段识别的异常行 |
| news_by_company | 按企业统计新闻数量 |
| news_by_source | 按来源统计新闻数量 |
| news_by_month | 按月份统计新闻数量 |
| news_abnormal_short | 摘要内容过短的新闻 |

---

## 4. 环境依赖

建议使用 Python 3.10 或以上版本。

安装依赖：

```bash
pip install pandas openpyxl tqdm openai
```

其中：

| 包 | 用途 |
|---|---|
| pandas | 数据读取、清洗、统计分析 |
| openpyxl | 保存 Excel 分析表 |
| tqdm | 显示 DeepSeek 批量摘要进度 |
| openai | 调用 DeepSeek API，DeepSeek API 兼容 OpenAI SDK |

---

## 5. DeepSeek API 配置

脚本通过环境变量读取 DeepSeek API Key。

### 5.1 Linux / macOS

```bash
export DEEPSEEK_API_KEY="你的DeepSeek API Key"
```

### 5.2 Windows PowerShell

```powershell
$env:DEEPSEEK_API_KEY="你的DeepSeek API Key"
```

脚本中使用的模型为：

```text
deepseek-v4-flash
```

DeepSeek 调用地址为：

```text
https://api.deepseek.com
```

---

## 6. 运行方式

将以下文件放在同一目录：

```text
run_clean_and_analyze.py
stock_daily.csv
news_cninfo.csv
news_eastmoney.csv
news_stcn.csv
```

然后运行：

```bash
python run_clean_and_analyze.py
```

脚本会依次执行：

1. 股票数据清洗
2. 新闻数据合并
3. 非智能体规则抽取新闻核心内容
4. 调用 DeepSeek 生成新闻摘要
5. 股票与新闻数据分析
6. 生成 Markdown 报告
7. 保存 Excel 分析表

---

## 7. 股票数据清洗方法

### 7.1 保留字段

清洗后的股票数据保留以下字段：

```text
StockCode, Date, Open, High, Low, Close, Adj Close, Volume
```

相比只保留行情字段，保留 `StockCode` 是必要的。否则无法判断每一条行情记录属于哪一只股票，也无法进行按公司或按股票代码的数据规模分析。

### 7.2 日期规范化

脚本将 `Date` 转换为统一格式：

```text
YYYY-MM-DD
```

这样便于后续按天、按月统计，也便于和新闻日期进行对齐。

### 7.3 数值类型转换

以下字段会被转换为数值类型：

```text
Open, High, Low, Close, Adj Close, Volume
```

如果某些值无法转换为数字，会被转为缺失值。

### 7.4 缺失值处理

脚本会删除关键字段缺失的记录。关键字段包括：

```text
StockCode, Date, Open, High, Low, Close, Volume
```

`Adj Close` 不作为强制删除条件，因为本项目主要分析的是不复权价格，`Adj Close` 只是参考字段。

### 7.5 异常值检查

股票清洗阶段检查以下异常：

1. `Open <= 0`
2. `High <= 0`
3. `Low <= 0`
4. `Close <= 0`
5. `Volume < 0`
6. `High < max(Open, Low, Close)`
7. `Low > min(Open, High, Close)`

满足上述任一条件的记录会被放入：

```text
output/intermediate/stock_abnormal_rows.csv
```

正常记录会进入：

```text
output/stock_daily_cleaned.csv
```

### 7.6 重复值处理

若同一只股票在同一交易日期出现重复记录，即：

```text
StockCode + Date
```

重复，则保留第一条。

### 7.7 排序

清洗后的股票数据按照以下顺序排序：

```text
StockCode 升序，Date 升序
```

---

## 8. 新闻数据清洗方法

新闻数据采用两阶段处理方法：

```text
规则抽取核心内容 → DeepSeek 客观摘要
```

这样做的原因是新闻正文中经常包含大量噪声，例如公告免责声明、页眉页脚、文章来源和责任编辑等。如果直接把全文输入模型，容易导致摘要偏离新闻主体，也会增加 API 调用成本。

### 8.1 新闻合并

脚本读取三个新闻文件，并统一字段为：

```text
企业, 日期, 来源, 标题, URL, 原始正文
```

对不同来源的差异做兼容处理：

1. `企业名称` 统一为 `企业`
2. `发布时间` 统一为 `日期`
3. `摘要` 和 `正文` 合并为 `原始正文`
4. 缺失的 `URL` 或 `标题` 用空字符串填充

### 8.2 新闻去重

脚本按照以下字段进行基础去重：

```text
企业, 日期, 来源, 标题, URL
```

这可以去除完全重复或近似重复采集的新闻记录。

### 8.3 噪声删除

脚本会尝试删除以下噪声：

1. 港交所免责声明
2. 上市公司公告常见免责声明
3. 证券代码、证券简称、公告编号
4. 页码和页眉页脚
5. 文章来源
6. 原标题
7. 责任编辑
8. 免责声明

示例噪声包括：

```text
香港交易及结算所有限公司及香港联合交易所有限公司对本公告之内容概不负责
本公司董事会及全体董事保证本公告内容不存在任何虚假记载
证券代码：xxxx 证券简称：xxxx
文章来源：东方财富网
责任编辑：xxx
```

### 8.4 核心内容定位

脚本使用非智能体方法定位核心内容，主要依据三类信息：

#### 8.4.1 结构化标记

如果正文中出现以下结构化标记，则优先从这些位置开始抽取：

```text
重要内容提示
一、
二、
三、
本次公告
本次交易
本次会议
本次回购
本次投资
风险提示
```

#### 8.4.2 关键词

脚本会对段落进行关键词打分。关键词包括：

```text
公告、董事会、股东大会、议案、决议、披露、报告期、年度报告、季度报告
营收、收入、净利润、利润、亏损、同比、增长、下降、业务、订单、合同、项目
分红、派息、回购、增持、减持、融资、发行、债券、可转债
诉讼、仲裁、处罚、监管、问询、风险、违约、停牌、复牌
收购、出售、投资、合作、中标、签署、终止、变更、任命、辞职
```

#### 8.4.3 段落位置

普通新闻通常采用倒金字塔结构，重要信息更可能出现在正文前部。因此，脚本会对前 6 个段落略微加权。

### 8.5 核心内容长度限制

每条新闻最多截取 4000 个中文字符作为核心内容。这样可以控制 DeepSeek 调用成本，同时避免输入过长导致摘要质量下降。

---

## 9. DeepSeek 摘要方法

### 9.1 System Prompt

脚本使用如下系统提示词：

```text
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
```

### 9.2 User Prompt 模板

每条新闻使用如下用户提示词：

```text
请对以下财经新闻核心内容进行客观总结。

企业：{企业}
日期：{日期}
来源：{来源}
标题：{标题}

核心内容：
{核心内容}

请只输出总结后的内容，不要输出解释。
```

### 9.3 摘要输出规则

DeepSeek 输出内容会作为最终新闻表中的 `内容` 字段。

最终新闻表只保留：

```text
企业, 日期, 来源, 内容
```

---

## 10. 数据分析方法

## 10.1 股票数据规模分析

脚本会统计：

1. 股票数据总行数
2. 股票代码数量
3. 日期范围
4. 每只股票的记录数
5. 每只股票的开始日期和结束日期
6. 每只股票的收盘价均值、标准差、最大值、最小值
7. 每只股票的成交量均值和标准差

### 10.2 股票月度分布分析

按月份统计：

1. 每月记录数
2. 每月涉及的股票数量
3. 每月平均收盘价
4. 每月平均成交量

### 10.3 股票波动分析

脚本基于不复权收盘价 `Close` 计算日收益率：

```text
daily_return = 当前交易日 Close / 前一交易日 Close - 1
```

日收益率按 `StockCode` 分组计算，避免不同股票之间错误相连。

每只股票统计：

1. 日收益率均值
2. 日收益率标准差
3. 最大单日收益率
4. 最小单日收益率

### 10.4 股票异常波动分析

脚本识别两类异常波动：

1. 单日收益率绝对值超过 10%
2. 基于 IQR 方法识别成交量异常

IQR 方法如下：

```text
Q1 = 成交量 25% 分位数
Q3 = 成交量 75% 分位数
IQR = Q3 - Q1
异常阈值 = Q3 + 3 * IQR
```

如果某日成交量超过该阈值，则标记为成交量异常。

---

## 11. 新闻数据分析方法

### 11.1 新闻数据规模分析

脚本会统计：

1. 新闻总数
2. 企业数量
3. 来源数量
4. 新闻日期范围
5. 摘要内容长度均值
6. 摘要内容长度中位数
7. 摘要内容长度最大值
8. 摘要内容长度最小值

### 11.2 按企业统计

按企业统计：

1. 新闻数量
2. 最早新闻日期
3. 最晚新闻日期
4. 平均摘要长度

### 11.3 按来源统计

按来源统计：

1. 新闻数量
2. 平均摘要长度

### 11.4 按月份统计

按月份统计：

1. 新闻数量
2. 涉及企业数量

### 11.5 新闻异常检查

脚本将摘要内容长度少于 20 字的新闻标记为异常短摘要。

这类记录可能包括：

1. 原始新闻正文为空
2. 核心内容抽取失败
3. DeepSeek 调用失败
4. 原文信息过少

---

## 12. 注意事项

1. 股票清洗后的文件必须保留 `StockCode`。否则无法区分不同股票。
2. `Open/High/Low/Close` 是不复权价格，是股票分析的主字段。
3. `Adj Close` 虽然保留，但只是参考字段。
4. DeepSeek 摘要前必须先做规则核心内容抽取，避免全文噪声影响摘要质量。
5. 如果新闻数量很多，DeepSeek 调用可能耗时较长，并产生 API 成本。
6. 如果只想测试流程，可以先截取前 10 条新闻运行。
7. 如果 DeepSeek 调用失败，脚本会重试 3 次，仍失败则写入“模型调用失败，未生成摘要”。

---

## 13. 新闻摘要修复逻辑

在完整摘要流程运行后，如果 `news_summarized.csv` 中出现空白摘要、模型调用失败、无法生成摘要，或者发现 `core_content` 抽取质量不好，需要先执行新闻摘要修复流程，再进入最终数据分析。

当前版本的修复流程不是重新处理全部新闻，而是只检测和修复坏样本：

```text
读取 news_core_content.csv
读取 news_summary_checkpoint.csv
按行号 row_index 对齐两者
检测坏摘要和坏 core_content
导出坏样本
对坏样本重新抽取 core_content
只对坏样本重新调用 DeepSeek
每修复一条立即写入修复 checkpoint
将修复结果覆盖回 output/news_summarized.csv
确认质量后再生成数据分析报告
```

### 13.1 为什么当前版本按行号对齐

`news_core_content.csv` 本身没有 `news_id` 字段，因此当前这批历史中间文件不能直接按 `news_id` 对齐。

当前采用按行号对齐：

```text
news_core_content.csv 第 i 行
对应
news_summary_checkpoint.csv 第 i 行
```

这样做的原因是两个文件来自同一次主流程，顺序一致：

```text
读取三个原始新闻文件
合并新闻
抽取 core_content
写出 news_core_content.csv
逐条调用 DeepSeek
按同一顺序写入 news_summary_checkpoint.csv
```

为了避免错配，修复脚本会做安全校验：

```text
1. news_core_content.csv 和 news_summary_checkpoint.csv 行数必须一致；
2. 企业、日期、来源必须逐行一致；
3. 如果校验失败，脚本直接报错，不继续修复。
```

### 13.2 为什么不需要重新匹配三个原始新闻文件

当前修复流程不需要重新回到：

```text
news_cninfo.csv
news_eastmoney.csv
news_stcn.csv
```

因为 `news_core_content.csv` 已经保存了重新抽取核心内容所需的信息：

```text
企业
日期
来源
标题
URL
原始正文
核心内容
```

重新抽取 `core_content` 时，脚本直接使用：

```text
标题 + 原始正文
```

因此，`news_core_content.csv` 本身就是“合并后的原始新闻 + 已抽取核心内容”的中间表。只有当该文件缺少 `原始正文` 列时，才需要重新回到三个原始文件进行匹配。

### 13.3 坏样本、坏摘要、坏 core_content 的区别

修复脚本会输出类似统计：

```text
坏样本数：1640
坏摘要数：1447
坏 core_content 数：915
```

这三个数不是相加关系，而是集合关系。

`坏样本数` 是最终需要重新处理的新闻行数。只要一条新闻存在“摘要坏”或“core_content 坏”，就会进入坏样本集合。

`坏摘要数` 表示摘要输出本身不可用，例如：

```text
摘要为空
摘要太短
模型调用失败，未生成摘要
原文信息不足，无法形成完整摘要
无法生成摘要
无法提取
无法判断
```

`坏 core_content 数` 表示规则抽取出来的核心内容质量不好，例如：

```text
核心内容为空
核心内容太短
核心内容只剩标题
原始正文很长，但核心内容只有一点点
```

一条新闻可能同时存在两个问题，所以：

```text
坏样本数 ≠ 坏摘要数 + 坏 core_content 数
```

例如：

```text
坏摘要数 + 坏 core_content 数 - 坏样本数
= 1447 + 915 - 1640
= 722
```

说明有 722 条新闻同时存在坏摘要和坏 core_content 问题。

进一步拆分为：

```text
仅摘要坏：1447 - 722 = 725
仅 core_content 坏：915 - 722 = 193
两者都坏：722
总坏样本：725 + 193 + 722 = 1640
```

### 13.4 坏样本判定规则

坏摘要判定规则：

```text
摘要为空
摘要长度小于 20 字
包含“模型调用失败”
包含“未生成摘要”
包含“无法形成完整摘要”
包含“无法生成摘要”
包含“原文信息不足”
包含“信息不足”
包含“无法总结”
包含“无法提取”
包含“无法判断”
包含“未提供”
输出过短且明显不是摘要，例如“工商”
```

坏 core_content 判定规则：

```text
核心内容为空
核心内容小于 50 字
核心内容等于标题，但原始正文很长
原始正文很长，但核心内容只比标题多一点点
```

### 13.5 修复版 core_content 抽取规则

当前修复脚本使用改进版核心内容抽取逻辑。主要变化如下：

1. 不再使用容易吞掉全文的贪婪正则，例如：

```text
证券代码.*证券简称.*
```

2. 只删除高置信短噪声，例如：

```text
港交所免责声明
上市公司公告免责声明
页码
责任编辑
文章来源
```

3. 对公告、年报、季报、股东大会、权益分派、募集资金等长文本，优先定位重要章节附近内容，例如：

```text
重大事项提示
重要内容提示
主要会计数据和财务指标
管理层讨论与分析
利润分配方案
本次发行
募集资金
风险提示
股东大会
权益分派
回购股份
业绩说明会
```

4. 对正文切分后的信息单元进行关键词打分，优先保留包含金额、比例、时间、业务事项、会议事项、发行事项、分红事项、回购事项的内容。

5. 对正文前部段落适当加权，因为财经新闻和公告的重要信息通常靠前。

6. 对委任代表表格、投票表格、签名说明等低价值内容降权。

### 13.6 修复阶段 DeepSeek Prompt

修复阶段使用比初始摘要更宽容的提示词，避免模型因为公告类文本信息不完整而直接输出“原文信息不足”。

System Prompt 核心要求：

```text
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
```

User Prompt 模板：

```text
请修复下面这条财经新闻摘要。

企业：{企业}
日期：{日期}
来源：{来源}
标题：{标题}

原摘要：
{原摘要}

重新抽取的核心内容：
{修复后核心内容}

请只输出修复后的摘要，不要输出解释。
```

### 13.7 修复脚本与运行方式

当前修复脚本建议使用：

```text
repair_bad_news_summaries_by_row_overwrite.py
```

它会按行号对齐坏样本，并在修复完成后直接覆盖：

```text
output/news_summarized.csv
```

这样后续可以继续运行原有数据分析脚本，不需要修改输入路径。

只检测坏样本，不调用 DeepSeek：

```bash
uv run repair_bad_news_summaries_by_row_overwrite.py --detect-only
```

小样本测试：

```bash
uv run repair_bad_news_summaries_by_row_overwrite.py --limit 20
```

正式修复全部坏样本：

```bash
uv run repair_bad_news_summaries_by_row_overwrite.py
```

### 13.8 修复阶段断点续跑

修复阶段支持断点续跑。每完成一条坏样本修复，脚本会立即写入：

```text
output/intermediate/news_summary_repair_checkpoint_by_row.csv
```

如果程序中断，下次重新运行：

```bash
uv run repair_bad_news_summaries_by_row_overwrite.py
```

脚本会自动读取修复 checkpoint，跳过已经修复合格的行，只继续处理剩余坏样本。

如果想强制重新修复，可以使用：

```bash
uv run repair_bad_news_summaries_by_row_overwrite.py --force
```

或者删除：

```text
output/intermediate/news_summary_repair_checkpoint_by_row.csv
```

再重新运行。

### 13.9 覆盖 `news_summarized.csv` 与备份机制

当前版本修复完成后，会直接覆盖：

```text
output/news_summarized.csv
```

这样后续可以直接运行原来的数据分析脚本。

覆盖前会自动备份旧文件到：

```text
output/repair/news_summarized_before_repair_backup.csv
```

如果 `news_summarized.csv` 正在被 Excel、WPS、VS Code 或其他程序打开，Windows 可能会拒绝覆盖。此时需要先关闭文件，再重新运行脚本。


### 13.10 推荐最终运行顺序

当前版本推荐按以下顺序运行：

```text
1. 运行主清洗和摘要脚本
2. 如果发现日期为空，先运行 fix_news_dates_from_raw.py
3. 运行 repair_bad_news_summaries_by_row_overwrite.py --detect-only 检查坏样本
4. 运行 repair_bad_news_summaries_by_row_overwrite.py 正式修复坏样本
5. 检查 output/news_summarized.csv 中是否还有空白摘要或“无法生成摘要”
6. 确认摘要质量后，再运行数据分析部分
```

最终用于数据分析的新闻文件是：

```text
output/news_summarized.csv
```
