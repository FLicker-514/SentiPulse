<template>
  <div>
    <h2>超参数与模型配置</h2>
    <table class="tbl">
      <tr><th>BERT 微调</th><th>值</th><th>LSTM 预测</th><th>值</th></tr>
      <tr><td>学习率</td><td>2e-5</td><td>序列长度</td><td>60 天</td></tr>
      <tr><td>Batch Size</td><td>16 / 32</td><td>LSTM 层</td><td>100→100</td></tr>
      <tr><td>训练轮数</td><td>3</td><td>优化器</td><td>Adam</td></tr>
      <tr><td>最大长度</td><td>256</td><td>归一化</td><td>MinMaxScaler</td></tr>
      <tr><td>权重衰减</td><td>0.01</td><td>训练/测试</td><td>&lt; 2024 / ≥ 2024</td></tr>
    </table>
  </div>
</template>
<style scoped>
h2 { font-size: 40px; font-weight: 700; color: #e8c97a; border-bottom: 3px solid #c8963e; padding-bottom: 6px; margin: 18px 0 12px; }
h2:first-child { margin-top: 0; }
.tbl { width: 100%; border-collapse: collapse; font-size: 20px; margin: 10px 0; }
.tbl th { background: rgba(0,0,0,0.4); color: #e8c97a; padding: 10px 14px; text-align: center; font-size: 18px; }
.tbl td { padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: center; }
.tbl tr:nth-child(even) td { background: rgba(255,255,255,0.08); }
</style>
