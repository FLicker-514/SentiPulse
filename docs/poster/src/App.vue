<template>
  <div class="poster">
    <PosterHeader />
    <MetricsStrip />
    <div class="main">
      <div class="col col-1">
        <SectionBackground />
        <SectionDataPipeline />
        <SectionHyperparams />
        <SectionNewsDist />
      </div>
      <div class="col col-2">
        <SectionBertFinetune />
        <SectionLstm />
      </div>
      <div class="col col-3">
        <SectionCharts />
        <SectionTeam />
      </div>
    </div>
    <PosterFooter />
  </div>
</template>

<script setup lang="ts">
import PosterHeader from './components/PosterHeader.vue'
import MetricsStrip from './components/MetricsStrip.vue'
import SectionBackground from './components/SectionBackground.vue'
import SectionDataPipeline from './components/SectionDataPipeline.vue'
import SectionBertFinetune from './components/SectionBertFinetune.vue'
import SectionLstm from './components/SectionLstm.vue'
import SectionCharts from './components/SectionCharts.vue'
import SectionHyperparams from './components/SectionHyperparams.vue'
import SectionNewsDist from './components/SectionNewsDist.vue'
import SectionTeam from './components/SectionTeam.vue'
import PosterFooter from './components/PosterFooter.vue'
</script>
