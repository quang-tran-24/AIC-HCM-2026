<script setup>
  import SearchView from '../components/SearchView.vue';
  import ContentView from '../components/ContentView.vue'
  import { useIPStore } from '@/stores/IP'
  import { useRouter } from 'vue-router'
  import { onMounted, onUnmounted, ref } from 'vue'
  import { API } from '@/api/retrieval';
  const myrouter = useRouter()
  const ipStore = useIPStore()

  async function loadIP() {
    if (ipStore.isIPSet()) {
      let ip = ipStore.getIP()
      console.log('IP is set:', ip)

      let check = await API.loadAPI()
      if (check && check['status']===200) {
        alert('Kết nối thành công tới IP: ' + ip)
      } else {
        myrouter.replace({ path: '/kpt' })
      }

    } else {
      console.log('IP is not set')
      myrouter.replace({ path: '/kpt' })
    }
  }

  let hasLoaded = false

  const searchRef = ref(null)

  function handleKeydown(evt) {
    if (!evt) return

    if (evt.key === 'Enter') {
      // don't trigger search when typing inside inputs/textareas
      const active = document.activeElement && document.activeElement.tagName
      if (active === 'INPUT' || active === 'TEXTAREA') return
      try {
        searchRef.value && searchRef.value.Search && searchRef.value.Search()
      } catch (e) {
        console.error('Error calling Search from KPTView:', e)
      }
    }
  }

  onMounted(async () => {
    if (!hasLoaded) {
      hasLoaded = true
      await loadIP()
    }
    window.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
  })
</script>

<template>
  <div class="bg-blue-500 text-white px-4 py-2 rounded ip-change">
    <span class="icon">⚙️</span>
    <button  @click="()=>{
      ipStore.clearIP()
      $router.push('/kpt')}">
      <span class="label">Đổi IP</span>
    </button>
  </div>
  <div class="main">
    <SearchView ref="searchRef" />
    <ContentView />
  </div>
</template>


<style scoped>
  body {
    margin: 0;
    padding: 0;
    height: 100vh;
    width: 100vw;
    font-family: Arial, sans-serif;
  }
  .main{
    height: 100vh;
    display: flex;
    background-color: #111;
    flex-direction: row;
  }
 .ip-change {
    position: absolute;
    top: 10px;
    right: 15px;
    z-index: 1000;
    width: 40px;
    overflow: hidden;
    white-space: nowrap;
    transition: width 0.5s ease;
    border-radius: 100px;
    padding: 10px 0;
    padding-left: 10px;
    padding-left: 10px;
  }

  .ip-change:hover {
    width: 100px;
  }

  .ip-change .label {
    opacity: 0;
    transition: opacity 0.3s ease;
  }

  .ip-change:hover .label {
    margin-left: 5px;
    opacity: 1;
  }

</style>
