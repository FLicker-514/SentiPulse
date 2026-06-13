<template>
  <div>
    <h2>BERT 金融情感微调</h2>
    <p>基座 <strong>bert-base-chinese</strong>，数据集 <strong>FinanceMTEB/FinFE</strong>（13,641 训练 / 1,516 验证 / 1,000 测试），三分类。</p>
    <img class="c" src="/training_loss.png" alt="训练损失">
    <table class="tbl">
      <tr><th>Epoch</th><th>Train Loss</th><th>Val Loss</th><th>Acc</th><th>Macro F1</th></tr>
      <tr><td>1</td><td>0.594</td><td>0.611</td><td>75.7%</td><td>73.1%</td></tr>
      <tr><td>2</td><td>0.431</td><td>0.607</td><td>77.3%</td><td>75.5%</td></tr>
      <tr><td class="win">3</td><td class="win">0.310</td><td>0.664</td><td class="win">78.6%</td><td class="win">76.8%</td></tr>
    </table>
    <h3>微调 vs 零样本基线（测试集）</h3>
    <img class="c" src="/bert_comparison.png" alt="对比">
    <p class="boost">Accuracy <span>+57.3pp</span> · Macro F1 <span>+59.7pp</span> · Weighted F1 <span>+64.8pp</span></p>
    <p class="note">微调前低于随机(33%)，微调后突破80%。</p>
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
.win { color: #5eead4; font-weight: 700; }
.boost { font-size: 22px; margin: 6px 0; }
.boost span { color: #5eead4; font-weight: 700; }
.note { font-size: 20px; color: #94a3b8; }
</style>
