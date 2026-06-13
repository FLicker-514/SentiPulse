<template>
  <div>
    <h2>团队分工 & 进度</h2>
    <div class="tg">
      <div class="card" v-for="m in members" :key="m.name">
        <div class="name">{{ m.name }}</div><div class="role">{{ m.role }}</div><div class="desc">{{ m.desc }}</div>
      </div>
    </div>
    <div class="gantt">
      <div class="gh"><span></span><span>W1</span><span>W2</span><span>W3</span><span>W4</span><span>W5</span></div>
      <div class="gr" v-for="r in ganttRows" :key="r.name">
        <span class="mem">{{ r.name }}</span>
        <span v-for="(t,i) in r.tasks" :key="i" class="cell" :class="r.color">{{ t }}</span>
      </div>
    </div>
    <div class="leg">
      <span v-for="l in legend" :key="l.name"><span class="dot" :style="{background:l.color}"></span>{{ l.name }}</span>
    </div>
    <h2>关键贡献</h2>
    <div class="clist">
      <p><strong>多源异构融合：</strong>4个公开来源、2种模态，全部自主采集</p>
      <p><strong>完整数据链路：</strong>爬取→清洗→摘要→特征→建模，可复现</p>
      <p><strong>严谨消融实验：</strong>3组对照，隔离情感信号贡献</p>
      <p><strong>可解释评估：</strong>滚动回测 + 年滚动 + 多维度指标</p>
      <p><strong>微调必要性验证：</strong>未微调 BERT 引入噪声反使 MAE 升至 11.27，证明领域微调是融合前提</p>
      <p><strong>端到端系统工程：</strong>从爬虫到前端界面，全链路可复现</p>
    </div>
    <h2>技术栈</h2>
    <p class="tags">
      <span class="t gold">Python 3.10+</span><span class="t blue">PyTorch</span><span class="t teal">TensorFlow</span>
      <span class="t blue">Transformers</span><span class="t teal">pandas</span><span class="t gold">Playwright</span>
      <span class="t blue">Flask+React</span><span class="t teal">DeepSeek</span><span class="t gold">Baostock</span>
      <span class="t blue">PyMuPDF</span><span class="t teal">uv/Conda</span>
    </p>
  </div>
</template>
<script setup lang="ts">
const members=[
  {name:'杨子龙',role:'项目负责人 & 算法',desc:'BERT微调 · LSTM训练 · 实验统筹'},
  {name:'罗力',role:'数据工程负责人',desc:'框架搭建 · 环境管理 · 文档总结'},
  {name:'薛皓天',role:'评估与分析负责人',desc:'回测评估 · 消融实验 · 可视化'},
  {name:'左凌旭',role:'工程与交付负责人',desc:'数据采集 · Pipeline · 前后端'},
]
const ganttRows=[
  {name:'杨子龙',color:'yl',tasks:['统筹方向','微调方案','代码固化','实验整合','收尾展示']},
  {name:'罗力',color:'ll',tasks:['框架搭建','数据适配','脚本参数','产物文档','报告材料']},
  {name:'薛皓天',color:'xh',tasks:['指标讨论','分析整理','数据清理','评估结果','实验结论']},
  {name:'左凌旭',color:'zl',tasks:['采集启动','爬虫扩展','维护文档','工程整理','README']},
]
const legend=[
  {name:'杨子龙',color:'#3b82f6'},{name:'罗力',color:'#8b5cf6'},
  {name:'薛皓天',color:'#f59e0b'},{name:'左凌旭',color:'#10b981'},
]
</script>
<style scoped>
h2 { font-size: 40px; font-weight: 700; color: #e8c97a; border-bottom: 3px solid #c8963e; padding-bottom: 6px; margin: 18px 0 12px; }
h2:first-child { margin-top: 0; }
.clist p { font-size: 22px; color: #e2e8f0; line-height: 1.6; margin-bottom: 5px; }
.tg { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 10px 0; }
.card { background: rgba(255,255,255,0.08); padding: 14px 16px; border-radius: 8px; border-top: 4px solid #0d9488; }
.card .name { font-weight: 700; color: #e8c97a; font-size: 21px; }
.card .role { color: #0d9488; font-weight: 600; font-size: 16px; }
.card .desc { color: #94a3b8; font-size: 16px; margin-top: 3px; }
.gantt { margin: 12px 0; }
.gh,.gr { display: grid; grid-template-columns: 80px repeat(5, 1fr); gap: 3px; margin-bottom: 4px; }
.gh span { text-align: center; font-size: 14px; font-weight: 700; color: #94a3b8; }
.gh span:first-child { text-align: left; }
.mem { font-size: 14px; font-weight: 600; color: #e8c97a; padding: 3px; }
.cell { padding: 4px 2px; border-radius: 4px; text-align: center; font-size: 12px; font-weight: 600; color: white; min-height: 28px; display: flex; align-items: center; justify-content: center; }
.cell.yl { background: #3b82f6; }
.cell.ll { background: #8b5cf6; }
.cell.xh { background: #f59e0b; }
.cell.zl { background: #10b981; }
.leg { display: flex; gap: 14px; margin-top: 5px; }
.leg span { display: flex; align-items: center; gap: 4px; font-size: 14px; }
.dot { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.tags { line-height: 2.2; }
.t { display: inline-block; padding: 4px 14px; border-radius: 12px; font-size: 15px; font-weight: 600; margin: 2px 3px; }
.t.gold { background: #fef3c7; color: #92400e; }
.t.blue { background: #dbeafe; color: #1e40af; }
.t.teal { background: #ccfbf1; color: #0f766e; }
</style>
