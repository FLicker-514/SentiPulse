<template>
  <div>
    <h2>收益-风险特征</h2>
    <img class="c" src="/stock_volatility.png" alt="风险">
    <p class="note">气泡=成交量；绿=正收益，金=负收益。海光信息波动最大，工商银行最稳。</p>
    <h3>10只标的概览</h3>
    <table class="tbl">
      <tr><th>股票</th><th>均价</th><th>波动σ</th><th>股票</th><th>均价</th><th>波动σ</th></tr>
      <tr v-for="r in stockStats" :key="r[0]"><td v-for="c in r" :key="c">{{ c }}</td></tr>
    </table>
  </div>
</template>
<script setup lang="ts">
const stockStats = [
  ['贵州茅台','1455','68.8','海光信息','199.6','56.8'],
  ['工商银行','7.36','0.41','海天味业','39.4','2.33'],
  ['恒瑞医药','56.1','7.29','海尔智家','25.3','2.00'],
  ['金山办公','299.2','35.5','交通银行','7.27','0.41'],
  ['保利发展','7.46','1.00','国电南瑞','23.8','1.95'],
]
</script>
<style scoped>
h2 { font-size: 40px; font-weight: 700; color: #e8c97a; border-bottom: 3px solid #c8963e; padding-bottom: 6px; margin: 18px 0 12px; }
h2:first-child { margin-top: 0; }
h3 { font-size: 30px; font-weight: 700; color: #e2e8f0; margin: 14px 0 8px; }
.c { width: 100%; border-radius: 8px; margin: 10px 0; box-shadow: 0 2px 16px rgba(0,0,0,0.08); border: 1px solid rgba(255,255,255,0.1); }
.note { font-size: 16px; color: #94a3b8; margin-top: 6px; }
.tbl { width: 100%; border-collapse: collapse; font-size: 20px; margin: 10px 0; }
.tbl th { background: rgba(0,0,0,0.4); color: #e8c97a; padding: 8px 10px; text-align: center; font-size: 16px; }
.tbl td { padding: 8px 10px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: center; }
.tbl tr:nth-child(even) td { background: rgba(255,255,255,0.08); }
</style>
