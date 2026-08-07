<script setup>
import { RouterView } from 'vue-router'
import { useOverlayStore } from '@/stores/overlay'
const overlay = useOverlayStore()

</script>

<template>
  <RouterView />
  <div v-if="overlay.isOpen" class="overlay-backdrop" @click.self="overlay.close()" @contextmenu.prevent.self="overlay.close()">
    <img
      :src="overlay.src"
      class="overlay-image"
      alt="zoomed"
      @click="(e) => { overlay.close() }"
      @contextmenu.prevent="overlay.close()"
    />
  </div>
</template>

<style>
  .overlay-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.85);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .overlay-image {
    max-width: 80vw;
    max-height: 80vh;
    scale: 2.0;
    box-shadow: 0 10px 30px rgba(0,0,0,0.6);
    border-radius: 0px;
    border-color: azure;
    border-width: 1px;
    border-style: solid;
  }
</style>
