import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useOverlayStore = defineStore('overlay', () => {
  const isOpen = ref(false)
  const src = ref('')

  function open(url) {
    src.value = url || ''
    isOpen.value = !!src.value
  }

  function close() {
    isOpen.value = false
    src.value = ''
  }

  return { isOpen, src, open, close }
})
