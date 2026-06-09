<template>
  <Layout>
    <div class="page-shell knowledge-retrieval-page">
      <div class="page-intro">
        <h1 class="page-intro-title">知识检索</h1>
        <p class="page-intro-subtitle">普通检索验证召回效果；智能检索通过路由、评估与改写闭环生成回答。</p>
      </div>

      <div class="retrieval-mode-segment" role="tablist" aria-label="检索模式">
        <router-link
          :to="{ name: 'retrieval' }"
          class="retrieval-mode-btn"
          :class="{ active: activeTab === 'classic' }"
          role="tab"
          :aria-selected="activeTab === 'classic'"
        >
          普通检索
        </router-link>
        <router-link
          :to="{ name: 'retrieval-agentic' }"
          class="retrieval-mode-btn"
          :class="{ active: activeTab === 'agentic' }"
          role="tab"
          :aria-selected="activeTab === 'agentic'"
        >
          智能检索
        </router-link>
      </div>

      <router-view />
    </div>
  </Layout>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import Layout from '../components/Layout.vue'

const route = useRoute()

const activeTab = computed(() => (route.name === 'retrieval-agentic' ? 'agentic' : 'classic'))
</script>

<style scoped>
.knowledge-retrieval-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-intro-title {
  margin: 0 0 8px;
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--text-primary);
}

.page-intro-subtitle {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.retrieval-mode-segment {
  display: inline-flex;
  align-self: flex-start;
  padding: 4px;
  border-radius: 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  gap: 2px;
}

.retrieval-mode-btn {
  border: none;
  margin: 0;
  padding: 8px 18px;
  border-radius: 9px;
  font-size: 0.88rem;
  font-weight: 500;
  color: var(--text-primary);
  background: transparent;
  cursor: pointer;
  text-decoration: none;
  transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}

.retrieval-mode-btn:hover {
  color: var(--brand-primary);
}

.retrieval-mode-btn.active {
  background: var(--bg-secondary);
  color: var(--brand-primary);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}
</style>
