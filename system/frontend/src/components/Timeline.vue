<template>
  <div class="timeline">
    <button class="btn btn-sm play-btn" @click="$emit('toggle')">{{ playing ? '暂停推演' : '播放推演' }}</button>
    <button class="btn btn-sm" @click="$emit('step', -1)">上一步</button>
    <button class="btn btn-sm" @click="$emit('step', 1)">下一步</button>
    <span class="time mono">{{ time }}</span>
    <input
      class="range"
      type="range"
      min="0"
      :max="max"
      :value="modelValue"
      @input="$emit('update:modelValue', Number($event.target.value))"
    />
    <span class="time mono">{{ endTime }}</span>
    <span class="progress mono">{{ modelValue }} / {{ max }}</span>
    <select class="select speed" :value="speed" @change="$emit('speed', Number($event.target.value))">
      <option :value="0.5">0.5×</option>
      <option :value="1">1×</option>
      <option :value="2">2×</option>
      <option :value="4">4×</option>
    </select>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: Number, default: 0 },
  max: { type: Number, default: 0 },
  time: { type: String, default: '' },
  endTime: { type: String, default: '' },
  playing: { type: Boolean, default: false },
  speed: { type: Number, default: 1 }
})
defineEmits(['update:modelValue', 'toggle', 'step', 'speed'])
</script>

<style scoped>
.timeline { display: flex; align-items: center; gap: 10px; }
.play-btn { min-width: 92px; border-color: var(--accent); color: #dff8ff; background: rgba(24, 85, 112, .55); }
.range { flex: 1; accent-color: var(--accent-2); height: 6px; cursor: pointer; }
.time { font-size: 14px; color: var(--text-2); min-width: 52px; text-align: center; }
.progress { font-size: 14px; color: var(--muted); min-width: 66px; text-align: right; }
.speed { width: 82px; height: 34px; font-size: 14px; }
</style>
