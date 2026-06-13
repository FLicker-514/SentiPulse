<template>
  <div class="hdr">
    <div class="dots"></div>
    <div class="inner">
      <div class="top">
        <div class="l">
          <h1><span class="accent">SentiPulse</span></h1>
          <h1 class="cn">舆情脉动</h1>
          <p class="sub">多源异构数据融合 · 金融情感推理 · LSTM 股价预测 · 端到端可复现系统</p>
        </div>
        <div class="r">
          <p class="course">数据挖掘与分析 课程项目</p>
          <p>课程编号 42040401 · 2026年6月</p>
          <p>指导教师：赵钦佩</p>
        </div>
      </div>
    </div>
  </div>
</template>
<style scoped>
.hdr { background: linear-gradient(135deg, #0a1835 0%, #122450 30%, #1a3368 50%, #122450 70%, #0a1835 100%); color: white; padding: 42px 72px 36px; position: relative; overflow: hidden; }
.hdr::before { content: ''; position: absolute; top: -50%; right: -20%; width: 600px; height: 600px; border-radius: 50%; background: radial-gradient(circle, rgba(200,150,62,0.12) 0%, transparent 60%); pointer-events: none; }
.hdr::after { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 5px; background: #c8963e; }
.dots { position: absolute; top: 20px; right: 40px; width: 200px; height: 120px; pointer-events: none; background-image: radial-gradient(circle, rgba(200,150,62,0.15) 2px, transparent 2px); background-size: 24px 24px; }
.inner { position: relative; z-index: 1; }
.top { display: flex; justify-content: space-between; align-items: flex-start; }
.l h1 { font-size: 192px; font-weight: 800; letter-spacing: 6px; line-height: 1.05; }
.l h1 .accent {
  background: linear-gradient(135deg, #ffd700 0%, #c8963e 40%, #e8c97a 70%, #ffd700 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.l h1.cn { font-size: 112px; color: white; margin-top: 4px; margin-bottom: 180px; }
.l .sub { font-size: 48px; font-weight: 300; color: #94a3b8; letter-spacing: 1px; margin-bottom: 20px; }
.r { text-align: right; font-size: 36px; color: #94a3b8; line-height: 1.9; }
.r .course { color: #e8c97a; font-weight: 600; font-size: 38px; }
</style>
