<template>
  <section class="surface-card usage-stats-section">
    <div class="usage-stats-grid">
      <UsageChartPanel v-model:range="range" />
      <ChatTop3Panel :range="range" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import type { DashboardUsageRange } from '../../api/dashboard'
import ChatTop3Panel from './ChatTop3Panel.vue'
import UsageChartPanel from './UsageChartPanel.vue'

const range = ref<DashboardUsageRange>('24h')
</script>

<style scoped>
.usage-stats-section {
  padding: 18px 20px;
}

.usage-stats-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 18px;
  align-items: stretch;
}

@media (max-width: 1100px) {
  .usage-stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
