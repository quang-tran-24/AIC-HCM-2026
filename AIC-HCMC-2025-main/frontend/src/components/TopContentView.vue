<script setup>

  import { ref, onMounted } from 'vue';
  import { useSelectedFramesStore } from '@/stores/selectedFrames'
  import { useOverlayStore } from '@/stores/overlay'

  const topFrameStore = useSelectedFramesStore()
  const overlay = useOverlayStore()

  onMounted(() => {
   const containers = document.querySelectorAll('.top-frames');
    containers.forEach(container => {
      let isDown = false;
      let startX;
      let scrollLeft;

      container.addEventListener('mousedown', e => {
        isDown = true;
        container.classList.add('active');
        startX = e.pageX - container.offsetLeft;
        scrollLeft = container.scrollLeft;
      });

      container.addEventListener('mouseleave', () => {
        isDown = false;
        container.classList.remove('active');
      });

      container.addEventListener('mouseup', () => {
        isDown = false;
        container.classList.remove('active');
      });

      container.addEventListener('mousemove', e => {
        if (!isDown) return;
        //e.preventDefault();
        const x = e.pageX - container.offsetLeft;
        const walk = (x - startX) *2;
        container.scrollLeft = scrollLeft - walk;
      });
    });
  });
</script>

<script>
  const path = new URL('../assets/pictures/wanwin.jpg', import.meta.url).href;

  const generateRandomId = () => {
    return Math.floor(10000 + Math.random() * 90000).toString(); // 5-digit string
  };

  export const similarFrames = ref(
    Array.from({ length: 10 }, () => ({
      video_name: 'L01_V001',
      keyframe_path: path,
      number: generateRandomId(),
      youtube: 'https://www.youtube.com/',
      similarity_score: +(Math.random() * 0.5 + 0.5).toFixed(2) // Optional: random 0.5–1.0
    }))
  );
</script>
<template>
  <div class="top-content">
    <div class="top-content-header">
      Top results
    </div>
    <div class="top-frames">
      <div
        v-for="(frame, idx) in similarFrames"
        :key="idx"
        class="top-frame"
      >
  <img
    :src="frame.keyframe_path"
    :class="topFrameStore.isSelected(frame.video_name, frame.number) ? 'select-img' : ''"
    @click="(e) => { if (e.shiftKey) { if (overlay.isOpen && overlay.src === frame.keyframe_path) { overlay.close() } else { overlay.open(frame.keyframe_path) } } else if (e.ctrlKey || e.metaKey) { const raw = frame.keyframe_path?.replace(/^src\/assets\//,'') || ''; if (raw) import('@/api/retrieval').then(m => m.API.contextSequence(raw)) } else { topFrameStore.toggleFrame(frame.video_name, frame.number, frame.keyframe_path) } }"
    @contextmenu.prevent="(e) => { if (overlay.isOpen && overlay.src === frame.keyframe_path) { overlay.close() } else { overlay.open(frame.keyframe_path) } }"
    draggable="false"
  />
        <div class="frame-info">
          <div class="video-name">{{ frame.video_name }}</div>
          <a :href="frame.youtube" class="frame-number">{{ frame.number }}</a>
          <div class="similarity-score">
            {{ (frame.similarity_score * 100).toFixed(2) }}%
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
  .top-content {
    margin-bottom: 30px;
    color: #fff;
  }

  .top-content-header {
    font-size: 20px;
    font-weight: bold;
    margin-bottom: 10px;
    color: #fff;
  }

  .top-frames {
    display: flex;
    gap: 6px;
    overflow-x: auto;
    padding: 0px;
    cursor: grab;
    user-select: none;
  }

  .top-frames.active {
    cursor: grabbing;
  }

  .top-frame {
    flex: 0 0 auto;
    width: 200px;
    background-color: #1e1e1e;
    border-radius: 8px;
    padding: 0px;
    text-align: center;
    color: #fff;
  }

  .top-frame .frame-img {
    width: 100%;
    height: auto;
    object-fit: cover;
    border-radius: 4px;
  }

  .frame-info {
    margin-top: 8px;
  }

  .video-name {
    font-size: 14px;
    font-weight: 500;
    color: #ddd;
  }

  .frame-number {
    font-size: 12px;
    font-weight: 500;
    color: #ddd;
  }

  .similarity-score {
    font-size: 12px;
    color: #aaa;
    margin-top: 4px;
  }

  .select-img{
      border: rgb(35, 210, 143) 4px solid;
      border-radius: 8px;
  }
</style>