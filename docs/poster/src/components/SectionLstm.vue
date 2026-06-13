<template>
  <div>
    <h2>LSTM 股价预测</h2>
    <table class="tbl">
      <tr><th>模式</th><th>输入特征 (seq=60)</th><th>情感来源</th></tr>
      <tr><td><strong>ts-only</strong></td><td>60日 Close</td><td>— 基线</td></tr>
      <tr><td><strong>fusion-bert</strong></td><td>60日 Close + signed_score</td><td>bert-base-chinese</td></tr>
      <tr><td><strong>fusion</strong></td><td>60日 Close + signed_score</td><td>FinBERT2-large</td></tr>
    </table>
    <p><strong>结构：</strong>LSTM(100) → LSTM(100) → Dense(1)，MinMaxScaler，预测下日收盘价。</p>
    <p><strong>情感特征：</strong>signed_score = P(pos) − P(neg) ∈ [−1, 1]，无新闻日补0。</p>
    <p><strong>切分：</strong>训练 &lt; 2024 / 测试 ≥ 2024。</p>
    <div class="info"><strong>创新：</strong>新闻→情感信号→LSTM辅助通道，<strong>多模态融合预测</strong>。</div>
    <h2>年滚动实验 & 评估</h2>
    <table class="tbl">
      <tr><th>折</th><th>训练集</th><th>测试年</th><th>累积天</th></tr>
      <tr v-for="r in yr" :key="r.fold"><td>{{ r.fold }}</td><td>{{ r.train }}</td><td>{{ r.test }}</td><td>{{ r.days }}</td></tr>
    </table>
    <p><strong>指标：</strong>MAE(7日均价) · MAE(第1日) · 方向准确率 · MAE(涨跌幅%)</p>
  </div>
</template>
<script setup lang="ts">
const yr=[
  {fold:1,train:'2021',test:'2022',days:'~243'},
  {fold:2,train:'2021–2022',test:'2023',days:'~485'},
  {fold:3,train:'2021–2023',test:'2024',days:'~727'},
  {fold:4,train:'2021–2024',test:'2025',days:'~970'},
  {fold:5,train:'2021–2025',test:'2026',days:'~1,213'},
]
</script>
<style scoped>
h2 { font-size: 40px; font-weight: 700; color: #e8c97a; border-bottom: 3px solid #c8963e; padding-bottom: 6px; margin: 18px 0 12px; }
h2:first-child { margin-top: 0; }
p { font-size: 22px; color: #e2e8f0; line-height: 1.6; margin-bottom: 6px; }
.tbl { width: 100%; border-collapse: collapse; font-size: 22px; margin: 10px 0; }
.tbl th { background: rgba(0,0,0,0.4); color: #e8c97a; padding: 10px 14px; text-align: center; font-size: 20px; }
.tbl td { padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: center; }
.tbl tr:nth-child(even) td { background: rgba(255,255,255,0.08); }
.info { background: rgba(255,255,255,0.08); border-left: 5px solid #c8963e; padding: 14px 18px; border-radius: 0 8px 8px 0; margin: 12px 0; font-size: 22px; color: #e2e8f0; line-height: 1.6; }
</style>
