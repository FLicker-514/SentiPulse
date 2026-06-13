<template>
  <div>
    <h2>消融实验结果</h2>
    <img class="c" src="/lstm_comparison.png" alt="LSTM消融对比">
    <p class="note">FinBERT fusion 全面优于基线：MAE(7日) 降低 5.3%，方向准确率提升 3.9pp。未微调 BERT 引入噪声反而有害。</p>
  </div>
</template>
<style scoped>
h2 { font-size: 40px; font-weight: 700; color: #e8c97a; border-bottom: 3px solid #c8963e; padding-bottom: 6px; margin: 18px 0 12px; }
h2:first-child { margin-top: 0; }
.c { width: 100%; border-radius: 8px; margin: 10px 0; box-shadow: 0 2px 16px rgba(0,0,0,0.08); border: 1px solid rgba(255,255,255,0.1); }
.note { font-size: 20px; color: #94a3b8; margin-top: 6px; }
</style>
