<template>
  <section class="page-header-card" :class="{ compact }">
    <div class="page-header-main">
      <span v-if="eyebrow" class="page-header-eyebrow">{{ eyebrow }}</span>
      <h2 class="page-header-title">{{ title }}</h2>
      <p v-if="description" class="page-header-description">{{ description }}</p>
      <div v-if="$slots.meta" class="page-header-meta">
        <slot name="meta" />
      </div>
    </div>

    <div v-if="$slots.actions" class="page-header-actions">
      <slot name="actions" />
    </div>
  </section>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    description?: string
    eyebrow?: string
    compact?: boolean
  }>(),
  {
    description: '',
    eyebrow: '',
    compact: false,
  },
)
</script>

<style scoped>
.page-header-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  padding: 28px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-elevated) 100%);
  box-shadow: var(--card-shadow-sm);
}

.page-header-card.compact {
  padding: 22px 24px;
}

.page-header-main {
  display: grid;
  gap: 10px;
}

.page-header-eyebrow {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.page-header-title {
  margin: 0;
  font-size: clamp(1.6rem, 2.5vw, 2.2rem);
  line-height: 1.15;
  color: var(--text-primary);
}

.page-header-description {
  margin: 0;
  max-width: 760px;
  color: var(--text-secondary);
  font-size: 0.98rem;
  line-height: 1.65;
}

.page-header-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.page-header-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 960px) {
  .page-header-card {
    flex-direction: column;
    align-items: stretch;
  }

  .page-header-actions {
    justify-content: flex-start;
  }
}
</style>
