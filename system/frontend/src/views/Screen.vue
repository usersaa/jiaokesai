<template>
  <Twin screen :record="record" />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Twin from './Twin.vue'

const route = useRoute()
const record = computed(() => route.query.record === '1')
</script>
