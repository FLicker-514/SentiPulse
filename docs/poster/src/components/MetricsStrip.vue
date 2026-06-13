<template>
  <div class="strip">
    <div class="item" v-for="m in metrics" :key="m.label">
      <div class="val">{{ m.value }}</div>
      <div class="lbl">{{ m.label }}</div>
    </div>
  </div>
</template>
<script setup lang="ts">
const metrics = [
  { value: '9,855', label: '新闻总条数' },
  { value: '10', label: 'A股龙头标的' },
  { value: '4', label: '异构数据源' },
  { value: '80.3%', label: 'BERT 测试准确率' },
  { value: '3', label: 'LSTM 消融对比组' },
  { value: '+64.8pp', label: '微调提升 (W-F1)' },
]
</script>
<style scoped>
.strip { display: grid; grid-template-columns: repeat(6, 1fr); background: #1a3368; }
.item { padding: 22px 16px; text-align: center; border-right: 1px solid rgba(255,255,255,0.06); }
.item:last-child { border-right: none; }
.val { font-size: 56px; font-weight: 800; color: #e8c97a; }
.lbl { font-size: 24px; color: #94a3b8; margin-top: 6px; }
</style>
