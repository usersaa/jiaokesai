<template>
  <div ref="el" :style="{ height, width: '100%' }"></div>
</template>

<script setup>
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  option: { type: Object, default: () => ({}) },
  height: { type: String, default: '280px' }
})

const el = ref(null)
let chart = null
let observer = null

function render() {
  if (chart) chart.setOption(props.option || {}, true)
}

function resize() {
  if (chart) chart.resize()
}

onMounted(() => {
  chart = echarts.init(el.value)
  render()
  observer = new ResizeObserver(resize)
  observer.observe(el.value)
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  if (observer) observer.disconnect()
  window.removeEventListener('resize', resize)
  if (chart) chart.dispose()
})

watch(() => props.option, render, { deep: true })
</script>
