<template>
  <div>
    <h2>数据采集与清洗流水线</h2>
    <p>团队<strong>不引用第三方成品数据集</strong>，所有价量与新闻通过自主爬虫获取。</p>
    <svg class="sv" viewBox="0 0 360 330" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="g1" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#1a3368"/><stop offset="100%" stop-color="#224488"/></linearGradient>
        <linearGradient id="g2" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#0d1b3e"/><stop offset="100%" stop-color="#122450"/></linearGradient>
        <marker id="arr" markerWidth="5" markerHeight="4" refX="3" refY="2" orient="auto">
          <polygon points="0 0, 5 2, 0 4" fill="#c8963e"/>
        </marker>
      </defs>

      <!-- Card 1: y=4, h=46 -->
      <rect x="15" y="4" width="330" height="46" rx="6" fill="url(#g1)"/>
      <text x="180" y="23" text-anchor="middle" fill="#e8c97a" font-size="12" font-weight="700">数据采集 · Data Collection</text>
      <text x="180" y="40" text-anchor="middle" fill="#94a3b8" font-size="10">Baostock 价量 · 东方财富 · 巨潮资讯 · 证券时报</text>
      <line x1="180" y1="55" x2="180" y2="63" stroke="#c8963e" stroke-width="1.3" marker-end="url(#arr)"/>

      <!-- Card 2: y=68, h=46 -->
      <rect x="15" y="68" width="330" height="46" rx="6" fill="#132450"/>
      <text x="180" y="87" text-anchor="middle" fill="#5eead4" font-size="12" font-weight="700">数据清洗与 LLM 摘要 · Cleaning</text>
      <text x="180" y="104" text-anchor="middle" fill="#94a3b8" font-size="10">规则去噪 → DeepSeek 客观摘要（均值 102 字/条）</text>
      <line x1="180" y1="119" x2="180" y2="127" stroke="#c8963e" stroke-width="1.3" marker-end="url(#arr)"/>

      <!-- Card 3: y=132, h=46 -->
      <rect x="15" y="132" width="330" height="46" rx="6" fill="url(#g1)"/>
      <text x="180" y="151" text-anchor="middle" fill="#5eead4" font-size="12" font-weight="700">情感特征构建 · Sentiment Features</text>
      <text x="180" y="168" text-anchor="middle" fill="#94a3b8" font-size="10">BERT / FinBERT2-large → signed_score 日度聚合</text>
      <line x1="180" y1="183" x2="180" y2="191" stroke="#c8963e" stroke-width="1.3" marker-end="url(#arr)"/>

      <!-- Card 4: y=196, h=46 -->
      <rect x="15" y="196" width="330" height="46" rx="6" fill="#132450"/>
      <text x="180" y="215" text-anchor="middle" fill="#e8c97a" font-size="12" font-weight="700">LSTM 模型训练 · Model Training</text>
      <text x="180" y="232" text-anchor="middle" fill="#94a3b8" font-size="10">ts-only · fusion-bert · fusion（三组消融对照）</text>
      <line x1="180" y1="247" x2="180" y2="255" stroke="#c8963e" stroke-width="1.3" marker-end="url(#arr)"/>

      <!-- Card 5: y=260, h=41 -->
      <rect x="15" y="260" width="330" height="41" rx="6" fill="url(#g1)"/>
      <text x="180" y="278" text-anchor="middle" fill="#5eead4" font-size="12" font-weight="700">回测评估 · Evaluation</text>
      <text x="180" y="294" text-anchor="middle" fill="#94a3b8" font-size="10">滚动回测 · 年滚动 · MAE/方向准确率 · Dashboard</text>

      <!-- Badge -->
      <rect x="90" y="308" width="180" height="20" rx="10" fill="#c8963e"/>
      <text x="180" y="322" text-anchor="middle" fill="white" font-size="11" font-weight="700">端到端可复现 Pipeline</text>
    </svg>
  </div>
</template>
<style scoped>
h2 { font-size: 40px; font-weight: 700; color: #e8c97a; border-bottom: 3px solid #c8963e; padding-bottom: 6px; margin: 18px 0 12px; }
h2:first-child { margin-top: 0; }
p { font-size: 22px; color: #e2e8f0; line-height: 1.6; margin-bottom: 6px; }
.sv { width: 100%; margin: 6px 0; }
</style>
