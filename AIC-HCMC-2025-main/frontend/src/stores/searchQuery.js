import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useSearchQueryStore = defineStore('searchQuery', () => {
  const transcription = ref('')
  const setTranscription = (val) => { transcription.value = (val ?? '').toString() }
  return { transcription, setTranscription }
})
