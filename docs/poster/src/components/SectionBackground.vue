<template>
  <div>
    <h2>研究背景与核心问题</h2>
    <p>A股市场受财经新闻、公司公告、行业政策等<strong>非结构化文本</strong>影响显著。传统股价预测仅依赖历史价量数据，难以捕捉市场情绪变化。</p>
    <div class="hl"><strong>核心问题：</strong>新闻情感能否提升 LSTM 预测精度？金融预训练 BERT 是否优于通用 BERT？</div>
    <h3>三大研究假设</h3>
    <ul>
      <li><strong>H₁：</strong>融合情感信息的 LSTM 优于纯价量 LSTM 基线</li>
      <li><strong>H₂：</strong>FinBERT2-large 情感特征优于通用 bert-base-chinese</li>
      <li><strong>H₃：</strong>两个情感模型在中文金融场景的判断存在系统差异</li>
    </ul>
  </div>
</template>
<style scoped>
h2 { font-size: 40px; font-weight: 700; color: #e8c97a; border-bottom: 3px solid #c8963e; padding-bottom: 6px; margin: 18px 0 12px; }
h2:first-child { margin-top: 0; }
h3 { font-size: 30px; font-weight: 700; color: #e2e8f0; margin: 14px 0 8px; }
p { font-size: 22px; color: #e2e8f0; line-height: 1.6; }
li { font-size: 22px; color: #e2e8f0; line-height: 1.6; margin-bottom: 5px; }
ul { padding-left: 24px; }
.hl { background: rgba(200,150,62,0.12); border: 1px solid rgba(200,150,62,0.3); padding: 14px 18px; border-radius: 8px; font-size: 22px; font-weight: 600; color: #e8c97a; margin: 12px 0; }
</style>
