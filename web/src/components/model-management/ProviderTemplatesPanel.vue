<template>
  <section class="panel templates-panel">
    <div class="panel-header">
      <div>
        <h2>可选模型模板</h2>
      </div>
    </div>

    <div class="search-box">
      <AppIcon name="search" class="search-icon" :size="16" />
      <input
        :value="keyword"
        class="search-input"
        type="text"
        placeholder="搜索厂商名称或代码"
        @input="emit('update:keyword', ($event.target as HTMLInputElement).value)"
      />
    </div>

    <div class="filter-group">
      <button
        v-for="item in filterOptions"
        :key="item.value"
        class="filter-chip"
        :class="{ active: activeType === item.value }"
        type="button"
        @click="emit('update:activeType', item.value)"
      >
        {{ item.label }}
      </button>
    </div>

    <div v-if="templates.length === 0" class="empty-state">没有匹配的厂商模板</div>

    <div v-else class="template-list">
      <button v-for="template in templates" :key="template.provider_code" class="template-card" type="button" @click="emit('create', template)">
        <div class="template-main">
          <span class="provider-mark">{{ getProviderMark(template.provider_name) }}</span>
          <div class="template-content">
            <div class="template-title-row">
              <h3>{{ template.provider_name }}</h3>
              <AppIcon name="arrow-up-right" class="launch-arrow" :size="16" />
            </div>
            <div class="tag-group">
              <span v-for="type in template.supported_types" :key="type" class="tag subtle-tag">
                {{ MODEL_TYPE_LABEL_MAP[type] }}
              </span>
            </div>
          </div>
        </div>
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { MODEL_TYPE_LABEL_MAP, MODEL_TYPE_ORDER, type ModelType, type ProviderTemplate } from '../../api/model-management'
import AppIcon from '../AppIcon.vue'

defineProps<{
  templates: ProviderTemplate[]
  keyword: string
  activeType: ModelType | 'all'
}>()

const emit = defineEmits<{
  create: [template: ProviderTemplate]
  'update:keyword': [value: string]
  'update:activeType': [value: ModelType | 'all']
}>()

const filterOptions = computed(() => [
  { value: 'all' as const, label: '全部' },
  ...MODEL_TYPE_ORDER.map((item) => ({ value: item, label: MODEL_TYPE_LABEL_MAP[item] })),
])

const getProviderMark = (providerName: string) => providerName.trim().slice(0, 1).toUpperCase() || 'A'
</script>

<style scoped>
.panel {
  display: grid;
  gap: 14px;
  padding: 22px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  box-shadow: var(--card-shadow-sm);
  font-size: var(--model-font-body, 12px);
}

.panel-header h2 {
  margin: 0;
  font-size: var(--model-font-title, 14px);
  color: var(--text-primary);
  line-height: 1.5;
}

.panel-header p {
  margin: 6px 0 0;
  color: var(--text-tertiary);
  font-size: var(--model-font-body, 12px);
}

.search-box {
  position: relative;
}

.search-icon {
  position: absolute;
  top: 50%;
  left: 12px;
  transform: translateY(-50%);
  color: var(--text-tertiary);
  pointer-events: none;
}

.search-input {
  width: 100%;
  height: 42px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  color: var(--text-primary);
  padding: 0 12px 0 38px;
}

.search-input:focus {
  outline: none;
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 4px var(--brand-primary-light);
  background: var(--bg-secondary);
}

.filter-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-chip {
  border: 1px solid var(--border-color);
  cursor: pointer;
  border-radius: 999px;
  padding: 7px 12px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-size: var(--model-font-chip, 10px);
  font-weight: 700;
  line-height: 1.4;
  transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}

.filter-chip.active {
  border-color: var(--brand-primary);
  background: var(--brand-primary-light);
  color: var(--brand-primary);
}

.template-list {
  display: grid;
  gap: 10px;
  max-height: calc(100vh - 320px);
  overflow: auto;
  padding-right: 4px;
}

.template-card {
  width: 100%;
  text-align: left;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: var(--bg-tertiary);
  padding: 16px;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.template-card:hover {
  transform: translateY(-1px);
  border-color: var(--brand-primary);
  background: var(--bg-secondary);
}

.template-main {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.provider-mark {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  font-weight: 700;
  flex-shrink: 0;
}

.template-content {
  min-width: 0;
  flex: 1;
  display: grid;
  gap: 10px;
}

.template-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.template-title-row h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--model-font-subtitle, 13px);
  font-weight: 600;
  line-height: 1.5;
}

.launch-arrow {
  color: var(--text-tertiary);
}

.tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: var(--model-font-chip, 10px);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  text-transform: uppercase;
  line-height: 1.4;
}

.empty-state {
  padding: 32px 0;
  text-align: center;
  color: var(--text-tertiary);
}
</style>
