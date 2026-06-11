# 新闻摘要修复报告

- 对齐方式：row_index
- 总样本数：9855
- 检测出的坏样本数：1640
- 已替换为合格修复摘要的数量：1596
- 修复后仍异常的摘要数量：44

说明：本脚本不依赖 news_id。它按行号对齐 news_core_content.csv 和 news_summary_checkpoint.csv。重新抽取 core_content 时，直接使用 news_core_content.csv 中保存的 原始正文 和 标题。