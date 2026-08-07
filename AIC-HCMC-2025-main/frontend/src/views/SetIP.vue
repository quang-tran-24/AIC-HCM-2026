<script setup>
  import { ref } from 'vue'
  import {useIPStore} from '@/stores/IP'
  import { useRouter } from 'vue-router'
  const name = ref('')
  const ipStore = useIPStore()
  const port = ref('')
  const ipAddress = ref('')
  const router = useRouter()

  function handleSubmit() {
    if (ipAddress.value === '' || port.value === '') {
      alert('Vui lòng nhập đầy đủ thông tin')
      return
    }
    if (isNaN(port.value) || port.value < 0 || port.value > 65535) {
      alert('Port không hợp lệ')
      return
    }
    ipStore.setIP(ipAddress.value+':'+port.value)
    console.log(ipAddress.value+':'+port.value)
    router.replace({ path: '/' })
  }
</script>

<template>
  <div class="min-h-screen bg-gray-900 text-white flex justify-center items-center">
    <div class="bg-gray-800 p-8 rounded-2xl shadow-xl w-full max-w-md">
      <h2 class="text-2xl font-bold mb-6 text-center text-teal-400">Thiết lập kết nối</h2>

      <div class="mb-4">
        <label class="block text-sm mb-1">Tên người dùng</label>
        <input
          v-model="name"
          type="text"
          placeholder="Nhập tên..."
          class="w-full px-4 py-2 bg-gray-700 text-white rounded-md focus:outline-none focus:ring-2 focus:ring-teal-400"
        />
      </div>

      <div class="mb-4">
        <label class="block text-sm mb-1">IP Backend</label>
        <input
          v-model="ipAddress"
          placeholder="Nhập IP..."
          class="w-full px-4 py-2 bg-gray-700 text-white rounded-md"
        />
      </div>

      <div class="mb-6">
        <label class="block text-sm mb-1">Port Backend</label>
        <input
          v-model="port"
          type="number"
          placeholder="Nhập port..."
          class="w-full px-4 py-2 bg-gray-700 text-white rounded-md focus:outline-none focus:ring-2 focus:ring-teal-400"
        />
      </div>

      <button
        @click="handleSubmit"
        class="w-full bg-teal-500 hover:bg-teal-600 text-black font-bold py-2 px-4 rounded-lg transition"
      >
        Kết nối
      </button>
    </div>
  </div>
</template>
