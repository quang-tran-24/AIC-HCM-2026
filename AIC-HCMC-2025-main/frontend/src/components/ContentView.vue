<script setup>
  import { onMounted, ref } from 'vue';
  import { useSelectedFramesStore } from '@/stores/selectedFrames'
  import TopContentView from '@/components/TopContentView.vue'
  import { useOverlayStore } from '@/stores/overlay'
  import { useSearchQueryStore } from '@/stores/searchQuery'
  const frameStore = useSelectedFramesStore()
  const overlay = useOverlayStore()
  const searchQuery = useSearchQueryStore()

  onMounted(() => {
    const containers = document.querySelectorAll('.video-frames');
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

  // const mockText = 
  // const generateFrames = (count) => {
  //   return Array.from({ length: count }, () => ({
  //     image: new URL('../assets/pictures/wanwin.jpg', import.meta.url).href,
  //     number: Math.floor(Math.random() * 10000), // or any range you prefer
  //   }));
  // };

  // const videos = [
  //   {
  //     title: "L03-V005",
  //     frames: generateFrames(10),
  //     text: mockText
  //   },
  //   {
  //     title: "L10-V023",
  //     frames: generateFrames(5),
  //     text: mockText
  //   }
  // ];

  function escapeHtml(str) {
    return (str ?? '').toString().replace(/[&<>"']/g, (ch) => {
      switch (ch) {
        case '&': return '&amp;'
        case '<': return '&lt;'
        case '>': return '&gt;'
        case '"': return '&quot;'
        case "'": return '&#39;'
        default: return ch
      }
    })
  }

  function toBaseStringWithMap(s) {
    const map = [] // normalized char index -> original index
    let out = ''
    for (let i = 0; i < s.length; i++) {
      const ch = s[i]
      const base = ch.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      if (!base) continue
      // take first base char to keep 1:1 mapping for indices
      out += base[0]
      map.push(i)
    }
    return { out, map }
  }

  function highlighted(text) {
    const original = (text ?? '').toString()
    const queryRaw = (searchQuery.transcription ?? '').toString().trim()
    if (!queryRaw) return escapeHtml(original)

    const { out: baseText, map } = toBaseStringWithMap(original)
    const baseQuery = queryRaw.normalize('NFD').replace(/[\u0300-\u036f]/g, '')

    const hay = baseText.toLowerCase()
    const needle = baseQuery.toLowerCase()
    if (!needle) return escapeHtml(original)

    // collect match ranges in original string indices
    const ranges = []
    let pos = 0
    while (true) {
      const idx = hay.indexOf(needle, pos)
      if (idx === -1) break
      const startOrig = map[idx]
      const endNorm = idx + needle.length
      const endOrig = endNorm < map.length ? map[endNorm] : original.length
      ranges.push([startOrig, endOrig])
      pos = idx + (needle.length || 1)
    }

    if (ranges.length === 0) return escapeHtml(original)

    // build escaped HTML with <mark> wrappers
    let html = ''
    let last = 0
    for (const [sIdx, eIdx] of ranges) {
      if (sIdx > last) html += escapeHtml(original.slice(last, sIdx))
      html += '<mark>' + escapeHtml(original.slice(sIdx, eIdx)) + '</mark>'
      last = eIdx
    }
    if (last < original.length) html += escapeHtml(original.slice(last))
    return html
  }
</script>

<script>
export const videos = ref([
    {
      title: "L03-V005",
      frames: [
  { image: new URL('../assets/pictures/wanwin.jpg', import.meta.url).href, keyframe_path: 'datasets/keyframes/L00_V000/0001.jpg', number: 1, youtube: 'https://www.youtube.com/' },
  { image: new URL('../assets/pictures/wanwin.jpg', import.meta.url).href, keyframe_path: 'datasets/keyframes/L00_V000/0002.jpg', number: 2, youtube: 'https://www.youtube.com/' },
  { image: new URL('../assets/pictures/wanwin.jpg', import.meta.url).href, keyframe_path: 'datasets/keyframes/L00_V000/0003.jpg', number: 3, youtube: 'https://www.youtube.com/' },
      ],
      text: "This is a sample text for video L03-V005."
    },
    {
      title: "L10-V023",
      frames: [
  { image: new URL('../assets/pictures/wanwin.jpg', import.meta.url).href, keyframe_path: 'datasets/keyframes/L00_V001/0004.jpg', number: 4 },
  { image: new URL('../assets/pictures/wanwin.jpg', import.meta.url).href, keyframe_path: 'datasets/keyframes/L00_V001/0005.jpg', number: 5 },
      ],
      text: "This is a sample text for video L10-V023."
    }
  ]);
</script>


<template>
  <div class="main-content">
    <TopContentView/>
    <div
      v-for="(video, vIdx) in videos"
      :key="vIdx"
      class="video-frame-container"
    >
      <div class="video-frame-header">{{ video.title }}</div>
      <div class="video-frames">
        <div
          v-for="(frame, fIdx) in video.frames"
          :key="fIdx"
          :class="['video-frame']"
        >
          <img
            :src="frame.image"
            :class="frameStore.isSelected(video.title, frame.number) ? 'select-img' : ''"
            @click="(e) => { if (e.shiftKey) { if (overlay.isOpen && overlay.src === frame.image) { overlay.close() } else { overlay.open(frame.image) } } else if (e.ctrlKey || e.metaKey) { const path = frame.keyframe_path || ''; if (path) import('@/api/retrieval').then(m => m.API.contextSequence(path)) } else { frameStore.toggleFrame(video.title, frame.number, frame.keyframe_path) } }"
            @contextmenu.prevent="(e) => { if (overlay.isOpen && overlay.src === frame.image) { overlay.close() } else { overlay.open(frame.image) } }"
            draggable="false"
          />
          <a
            v-if="frame.youtube"
            :href="frame.youtube"
            target="_blank"
            rel="noopener noreferrer"
            class="frame-number"
          >
            {{ frame.number }}
          </a>


        </div>
      </div>
  <div class="frame-text" v-html="highlighted(video.text)"></div>
    </div>
  </div>
</template>



<style scoped>
  .main-content {
    flex: 1;
    width: 72%;
    padding: 20px;
    overflow-y: auto;
    background-color: #141414;
    scrollbar-width: thin;
    scrollbar-color: #888 transparent;
  }
  .video-frame-container {
      margin-top: 0px;
      margin-bottom: 30px;
      color: #fff;
  }
  .video-frame-header {
      font-size: 20px;
      font-weight: bold;
      margin-bottom: 0px;
      color: #fff;
  }
  .video-frames {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      padding: 0px;
      cursor: grab;
      user-select: none;
  }
  .video-frames.active {
      cursor: grabbing;
  }
  .video-frame {
      flex: 0 0 auto;
      width: 250px;
      background-color: #1e1e1e;
      border-radius: 8px;
      padding: 0px;
      text-align: center;
      color: white;
  }
  .video-frame img {
      width: 100%;
      height: auto;
      object-fit: cover;
  }
  .frame-number {
      font-size: 16px;
      color: #ddd;
      text-align: center;
      margin-top: 10px;
      margin-bottom: 10px;
  }
  .frame-text {
      font-size: 14px;
      color: #ccc;
      margin-top: 10px;
      line-height: 1.4;
  }
  .frame-text mark {
      background: transparent;
      color: #4da6ff; /* emphasize in blue */
      font-weight: 600; /* semi-bold */
      text-decoration: underline;
  }
  .select-img{
      border: rgb(35, 210, 143) 4px solid;
      border-radius: 8px;
  }
</style>

