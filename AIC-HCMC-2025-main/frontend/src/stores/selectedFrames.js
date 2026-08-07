import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useSelectedFramesStore = defineStore('selectedFrames', () => {
  const selectedFrames = ref([])

  function toggleFrame(vIdx, fIdx, keyframe_paths) {
    const index = selectedFrames.value.findIndex(
      f => f.vIdx === vIdx && f.fIdx === fIdx
    )
    if (index === -1) {
      selectedFrames.value.push({ vIdx, fIdx, keyframe_paths })
    } else {
      selectedFrames.value.splice(index, 1)
    }
  }

  function isSelected(vIdx, fIdx) {
    return selectedFrames.value.some(f => f.vIdx === vIdx && f.fIdx === fIdx)
  }

  function clear(){
    selectedFrames.value = []
  }

  return { selectedFrames, toggleFrame, isSelected, clear }
})
