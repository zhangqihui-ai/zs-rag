<template>
  <div class="empty-state-card" :class="{ compact }">
    <div class="empty-state-icon">
      <slot name="icon">
        <AppIcon name="spark" :size="22" />
      </slot>
    </div>
    <div class="empty-state-copy">
      <h3>{{ title }}</h3>
      <p>{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="empty-state-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import AppIcon from './AppIcon.vue'

withDefaults(
  defineProps<{
    title: string
    description: string
    compact?: boolean
  }>(),
  {
    compact: false,
  },
)
</script>

<style scoped>
.empty-state-card {
  display: grid;
  justify-items: center;
  gap: 16px;
  padding: 40px 24px;
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--bg-secondary);
  text-align: center;
}

.empty-state-card.compact {
  padding: 24px 20px;
}

.empty-state-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 16px;
  background: var(--brand-primary-light);
  color: var(--brand-primary);
}

.empty-state-copy {
  display: grid;
  gap: 8px;
}

.empty-state-copy h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.05rem;
}

.empty-state-copy p {
  margin: 0;
  max-width: 420px;
  color: var(--text-secondary);
  line-height: 1.65;
}

.empty-state-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
}
</style>
