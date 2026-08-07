import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useIPStore = defineStore('IP', () => {
  const currentlyIP = ref(null)

  function setIP(ip) {
    currentlyIP.value = ip
  }
  function getIP() {
    return currentlyIP.value
  }
  function clearIP() {
    currentlyIP.value = null
    localStorage.removeItem('IP')
  }
  function isIPSet() {
    return currentlyIP.value !== null
  }

  return { setIP, getIP, clearIP, isIPSet, currentlyIP }
}, {
  persist: true 
})
