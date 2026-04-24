<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    :stroke-width="strokeWidth"
    aria-hidden="true"
  >
    <template v-if="name === 'brand'">
      <path d="M12 3 4 7.5 12 12l8-4.5L12 3Z" />
      <path d="M4 12.5 12 17l8-4.5" />
      <path d="M4 17.5 12 22l8-4.5" />
    </template>
    <template v-else-if="name === 'dashboard'">
      <path d="M4 13h6V4H4v9Z" />
      <path d="M14 20h6v-7h-6v7Z" />
      <path d="M14 10h6V4h-6v6Z" />
      <path d="M4 20h6v-3H4v3Z" />
    </template>
    <template v-else-if="name === 'knowledge'">
      <path d="M5 5.5A2.5 2.5 0 0 1 7.5 3H19v15.5A2.5 2.5 0 0 0 16.5 16H5V5.5Z" />
      <path d="M5 16v2.5A2.5 2.5 0 0 0 7.5 21H19" />
      <path d="M9 7h6" />
      <path d="M9 11h6" />
    </template>
    <template v-else-if="name === 'retrieval' || name === 'search'">
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4 4" />
    </template>
    <template v-else-if="name === 'chat'">
      <path d="M6 7.5A3.5 3.5 0 0 1 9.5 4h8A3.5 3.5 0 0 1 21 7.5v5A3.5 3.5 0 0 1 17.5 16H10l-4 4v-4.5A3.5 3.5 0 0 1 2.5 12V7.5A3.5 3.5 0 0 1 6 4" />
      <path d="M8 9h8" />
      <path d="M8 12.5h5" />
    </template>
    <template v-else-if="name === 'models'">
      <rect x="4" y="5" width="16" height="14" rx="3" />
      <path d="M8 9h8" />
      <path d="M8 12h8" />
      <path d="M8 15h4" />
    </template>
    <template v-else-if="name === 'settings'">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a1.7 1.7 0 0 1-2.4 2.4l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a1.7 1.7 0 0 1-3.4 0v-.2a1 1 0 0 0-.7-.9 1 1 0 0 0-1.1.2l-.1.1a1.7 1.7 0 0 1-2.4-2.4l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a1.7 1.7 0 0 1 0-3.4h.2a1 1 0 0 0 .9-.7 1 1 0 0 0-.2-1.1l-.1-.1a1.7 1.7 0 1 1 2.4-2.4l.1.1a1 1 0 0 0 1.1.2h.1A1 1 0 0 0 9 6.1V6a1.7 1.7 0 1 1 3.4 0v.1a1 1 0 0 0 .7.9 1 1 0 0 0 1.1-.2l.1-.1a1.7 1.7 0 0 1 2.4 2.4l-.1.1a1 1 0 0 0-.2 1.1v.1a1 1 0 0 0 .9.6H20a1.7 1.7 0 0 1 0 3.4h-.2a1 1 0 0 0-.4.1Z" />
    </template>
    <template v-else-if="name === 'workspace'">
      <path d="M4 7a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7Z" />
      <path d="M4 10h16" />
    </template>
    <template v-else-if="name === 'sun'">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2.5" />
      <path d="M12 19.5V22" />
      <path d="m4.9 4.9 1.8 1.8" />
      <path d="m17.3 17.3 1.8 1.8" />
      <path d="M2 12h2.5" />
      <path d="M19.5 12H22" />
      <path d="m4.9 19.1 1.8-1.8" />
      <path d="m17.3 6.7 1.8-1.8" />
    </template>
    <template v-else-if="name === 'moon'">
      <path d="M20 14.2A7.8 7.8 0 1 1 9.8 4 6.3 6.3 0 0 0 20 14.2Z" />
    </template>
    <template v-else-if="name === 'logout'">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="m16 17 5-5-5-5" />
      <path d="M21 12H9" />
    </template>
    <template v-else-if="name === 'plus'">
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </template>
    <template v-else-if="name === 'refresh'">
      <path d="M20 5v5h-5" />
      <path d="M4 19v-5h5" />
      <path d="M5.8 10A7 7 0 0 1 19 7.5L20 10" />
      <path d="M18.2 14A7 7 0 0 1 5 16.5L4 14" />
    </template>
    <template v-else-if="name === 'database'">
      <ellipse cx="12" cy="6" rx="7" ry="3" />
      <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
      <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
    </template>
    <template v-else-if="name === 'graph'">
      <circle cx="6" cy="8" r="2" />
      <circle cx="18" cy="6" r="2" />
      <circle cx="13" cy="17" r="2" />
      <path d="m7.7 9.1 3.5 5.1" />
      <path d="m16.1 7.1-2 7.8" />
      <path d="M8 8h8" />
    </template>
    <template v-else-if="name === 'send'">
      <path d="m3 11.8 17.2-7.3c.5-.2 1 .3.8.8L13.8 22c-.2.5-.9.4-.9-.1l-.6-7.2-7.1-.7c-.6 0-.7-.8-.2-1.1Z" />
      <path d="m12.5 14.5 7.1-7.1" />
    </template>
    <template v-else-if="name === 'spark'">
      <path d="m12 3 1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8L12 3Z" />
      <path d="m5 15 .8 2 .2.8.8.2L9 19l-2.2.8-.8 2.2-.8-2.2L3 19l2.2-.8L6 16l.2-.8.8-.2L5 15Z" />
    </template>
    <template v-else-if="name === 'folder'">
      <path d="M3 8a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8Z" />
    </template>
    <template v-else-if="name === 'server'">
      <rect x="4" y="4" width="16" height="6" rx="2" />
      <rect x="4" y="14" width="16" height="6" rx="2" />
      <path d="M8 7h.01" />
      <path d="M8 17h.01" />
      <path d="M12 7h6" />
      <path d="M12 17h6" />
    </template>
    <template v-else-if="name === 'user'">
      <circle cx="12" cy="8" r="4" />
      <path d="M5 20a7 7 0 0 1 14 0" />
    </template>
    <template v-else-if="name === 'arrow-up-right'">
      <path d="M7 17 17 7" />
      <path d="M9 7h8v8" />
    </template>
    <template v-else-if="name === 'close'">
      <path d="M6 6 18 18" />
      <path d="M18 6 6 18" />
    </template>
    <template v-else-if="name === 'chevron-down'">
      <path d="m6 9 6 6 6-6" />
    </template>
    <template v-else-if="name === 'status'">
      <path d="M5 14.5 9 10l3 3 7-7" />
      <path d="M4 20h16" />
    </template>
    <template v-else-if="name === 'shield'">
      <path d="M12 3 5 6v5c0 4.2 2.7 8.1 7 10 4.3-1.9 7-5.8 7-10V6l-7-3Z" />
      <path d="m9.5 12 1.7 1.7 3.8-3.8" />
    </template>
    <template v-else-if="name === 'sliders'">
      <path d="M4 6h6" />
      <path d="M14 6h6" />
      <circle cx="12" cy="6" r="2" />
      <path d="M4 12h10" />
      <path d="M18 12h2" />
      <circle cx="16" cy="12" r="2" />
      <path d="M4 18h2" />
      <path d="M10 18h10" />
      <circle cx="8" cy="18" r="2" />
    </template>
    <template v-else-if="name === 'panel'">
      <rect x="3" y="4" width="18" height="16" rx="3" />
      <path d="M9 4v16" />
      <path d="m13 10 3 2-3 2" />
    </template>
    <template v-else-if="name === 'bolt'">
      <path d="M13 2 5.5 13h4L8.5 22 18 10h-4L13 2Z" />
    </template>
    <template v-else-if="name === 'check'">
      <path d="m5 12 4 4L19 6" />
    </template>
    <template v-else-if="name === 'clock'">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v4l3 2" />
    </template>
    <template v-else-if="name === 'fullscreen'">
      <path d="M15 3h6v6" />
      <path d="M9 21H3v-6" />
      <path d="M21 3l-7 7" />
      <path d="M3 21l7-7" />
    </template>
    <template v-else-if="name === 'fullscreen-exit'">
      <path d="M8 3v5a2 2 0 0 1-2 2H3" />
      <path d="M16 21v-5a2 2 0 0 1 2-2h3" />
      <path d="M16 3v5a2 2 0 0 0 2 2h3" />
      <path d="M8 21v-5a2 2 0 0 0-2-2H3" />
    </template>
    <template v-else-if="name === 'grip'">
      <circle cx="9" cy="6" r="1.35" fill="currentColor" stroke="none" />
      <circle cx="9" cy="12" r="1.35" fill="currentColor" stroke="none" />
      <circle cx="9" cy="18" r="1.35" fill="currentColor" stroke="none" />
      <circle cx="15" cy="6" r="1.35" fill="currentColor" stroke="none" />
      <circle cx="15" cy="12" r="1.35" fill="currentColor" stroke="none" />
      <circle cx="15" cy="18" r="1.35" fill="currentColor" stroke="none" />
    </template>
    <template v-else>
      <circle cx="12" cy="12" r="8" />
    </template>
  </svg>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    name: string
    size?: number | string
    strokeWidth?: number | string
  }>(),
  {
    size: 18,
    strokeWidth: 1.8,
  },
)
</script>
