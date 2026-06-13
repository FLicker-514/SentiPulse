<template>
  <div>
    <h2>LSTM 消融实验</h2>
    <table class="tbl">
      <tr><th>模式</th><th>输入特征 (seq=60)</th><th>情感来源</th></tr>
      <tr><td><strong>ts-only</strong></td><td>60日 Close</td><td>— 基线</td></tr>
      <tr><td><strong>fusion-bert</strong></td><td>60日 Close + signed_score</td><td>bert-base-chinese (untuned)</td></tr>
      <tr><td><strong>fusion</strong></td><td>60日 Close + signed_score</td><td>FinBERT2-large (fine-tuned)</td></tr>
    </table>
    <p><strong>结构：</strong>LSTM(100)→LSTM(100)→Dense(1)，MinMaxScaler，预测下日收盘价。</p>
    <p><strong>情感特征：</strong>signed_score = P(pos) − P(neg) ∈ [−1, 1]。</p>
    <p><strong>训练/测试：</strong>2021–2025 训练 / 2026 测试，30轮，10股平均。</p>

    <h3>三组消融对比（10股平均）</h3>
    <img class="c" src="/lstm_comparison.png" alt="LSTM消融对比">
    <p class="note">FinBERT fusion 全面优于基线：MAE(7日) 降低 5.3%，方向准确率提升 3.9pp。未微调 BERT 则有害。</p>

    <h2>年滚动实验</h2>
    <img class="c" src="/year_roll.png" alt="年滚动实验">
    <p class="note">训练数据从1年扩展到5年，预测精度未单调改善——市场状态变化与新闻覆盖密度是关键。</p>
  </div>
</template>
<style scoped>
h2 { font-size: 40px; font-weight: 700; color: #e8c97a; border-bottom: 3px solid #c8963e; padding-bottom: 6px; margin: 18px 0 12px; }
h2:first-child { margin-top: 0; }
h3 { font-size: 30px; font-weight: 700; color: #e2e8f0; margin: 14px 0 8px; }
p { font-size: 22px; color: #e2e8f0; line-height: 1.6; margin-bottom: 6px; }
.c { width: 100%; border-radius: 8px; margin: 10px 0; box-shadow: 0 2px 16px rgba(0,0,0,0.08); border: 1px solid rgba(255,255,255,0.1); }
.tbl { width: 100%; border-collapse: collapse; font-size: 22px; margin: 10px 0; }
.tbl th { background: rgba(0,0,0,0.4); color: #e8c97a; padding: 10px 14px; text-align: center; font-size: 20px; }
.tbl td { padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: center; }
.tbl tr:nth-child(even) td { background: rgba(255,255,255,0.08); }
.note { font-size: 20px; color: #94a3b8; margin-top: 6px; }
</style>
