<template>
  <div>
    <h2>LSTM 消融实验设计</h2>
    <table class="tbl">
      <tr><th>模式</th><th>输入特征 (seq=60)</th><th>情感来源</th></tr>
      <tr><td><strong>ts-only</strong></td><td>60日 Close</td><td>— 基线</td></tr>
      <tr><td><strong>fusion-bert</strong></td><td>60日 Close + signed_score</td><td>bert-base-chinese (untuned)</td></tr>
      <tr><td><strong>fusion</strong></td><td>60日 Close + signed_score</td><td>FinBERT2-large (fine-tuned)</td></tr>
    </table>
    <p><strong>结构：</strong>LSTM(100)→LSTM(100)→Dense(1)，MinMaxScaler。</p>
    <p><strong>情感特征：</strong>signed_score = P(pos) − P(neg) ∈ [−1, 1]。</p>
    <p><strong>训练/测试：</strong>2021–2025 训练 / 2026 测试，30轮，10股平均。</p>
  </div>
</template>
<style scoped>
h2 { font-size: 40px; font-weight: 700; color: #e8c97a; border-bottom: 3px solid #c8963e; padding-bottom: 6px; margin: 18px 0 12px; }
h2:first-child { margin-top: 0; }
p { font-size: 22px; color: #e2e8f0; line-height: 1.6; margin-bottom: 6px; }
.tbl { width: 100%; border-collapse: collapse; font-size: 22px; margin: 10px 0; }
.tbl th { background: rgba(0,0,0,0.4); color: #e8c97a; padding: 10px 14px; text-align: center; font-size: 20px; }
.tbl td { padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: center; }
.tbl tr:nth-child(even) td { background: rgba(255,255,255,0.08); }
</style>
