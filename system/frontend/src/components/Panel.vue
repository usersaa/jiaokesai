<template>
  <section class="panel">
    <div v-if="title || $slots.extra" class="panel-head">
      <div class="panel-title">{{ title }}</div>
      <slot name="extra" />
    </div>
    <div class="panel-body" :style="{ padding: bodyPadding }">
      <slot />
    </div>
  </section>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  bodyPadding: { type: String, default: '18px 20px' }
})
</script>
