import axios from 'axios';
import { useIPStore } from '@/stores/IP';
import { videos } from '@/components/ContentView.vue';
import { similarFrames } from '@/components/TopContentView.vue'
const IPStore = useIPStore();

export const API = {
  quickSearch: async (text, transcription = '', ocr = '') => {
    try {
      const t = (text ?? '').toString().trim();
      const tc = (transcription ?? '').toString().trim();
      const o = (ocr ?? '').toString().trim();

      if (!t && !tc && !o) return; // nothing to search
      const res = await axios.post(`http://${IPStore.getIP()}/quick-search/`, {
        text: t || null,
        transcript: tc || null,
        ocr: o || null,
      })
      const mapped = res.data.rows.map(video => ({
        title: video.video_name,
        frames: video.keyframe_paths.map((path, idx) => ({
          image: `src/assets/${path}`,
          keyframe_path: path,
          number: video.keyframes[idx],
          youtube: video.youtube_links[idx],
        })),
        text: video.transcript,
      }))
      // Preserve context row at index 0 if present
      if (videos.value.length > 0 && videos.value[0].__isContext) {
        videos.value = [videos.value[0], ...mapped]
      } else {
        videos.value = mapped
      }
      similarFrames.value = res.data.similar_frames.map(frame => ({
        video_name: frame.video_name,
        keyframe_path: `src/assets/${frame.keyframe_path}`,
        number: frame.keyframe,
        youtube: frame.youtube_url,
        similarity_score: frame.similarity_score,
      }))
    } catch (error) {
      alert('Lỗi khi gửi yêu cầu: ' + error.message)
      console.error(error)
    }
  },

  // Temporal search using two consecutive texts
  temporalSearch: async (text1, text2) => {
    try {
      console.log('Temporal search:', text1, text2);
      const t1 = (text1 ?? '').toString().trim();
      const t2 = (text2 ?? '').toString().trim();
      if (!t1) return; // require first text
      const res = await axios.post(`http://${IPStore.getIP()}/temporal-search/`, {
        text1: t1,
        text2: t2,
      })

      const mapped = (res.data.rows || []).map(video => ({
        title: video.video_name,
        frames: video.keyframe_paths.map((path, idx) => ({
          image: `src/assets/${path}`,
          keyframe_path: path,
          number: video.keyframes[idx],
          youtube: video.youtube_links[idx],
        })),
        text: video.transcript,
      }))
      if (videos.value.length > 0 && videos.value[0].__isContext) {
        videos.value = [videos.value[0], ...mapped]
      } else {
        videos.value = mapped
      }
      if (res.data.similar_frames) {
        similarFrames.value = res.data.similar_frames.map(frame => ({
          video_name: frame.video_name,
          keyframe_path: `src/assets/${frame.keyframe_path}`,
          number: frame.keyframe,
          youtube: frame.youtube_url,
          similarity_score: frame.similarity_score,
        }))
      }
    } catch (error) {
      alert('Lỗi khi gửi yêu cầu: ' + error.message)
      console.error(error)
    }
  },

  SearchL26: async (text, transcription = '', ocr = '') => {
    try {
      const t = (text ?? '').toString().trim();
      const tc = (transcription ?? '').toString().trim();
      const o = (ocr ?? '').toString().trim();

      if (!t && !tc && !o) return; // nothing to search
      const res = await axios.post(`http://${IPStore.getIP()}/quick-search-l26/`, {
        text: t || null,
        transcript: tc || null,
        ocr: o || null,
      })
      const mapped = res.data.rows.map(video => ({
        title: video.video_name,
        frames: video.keyframe_paths.map((path, idx) => ({
          image: `src/assets/${path}`,
          keyframe_path: path,
          number: video.keyframes[idx],
          youtube: video.youtube_links[idx],
        })),
        text: video.transcript,
      }))
      // Preserve context row at index 0 if present
      if (videos.value.length > 0 && videos.value[0].__isContext) {
        videos.value = [videos.value[0], ...mapped]
      } else {
        videos.value = mapped
      }
      similarFrames.value = res.data.similar_frames.map(frame => ({
        video_name: frame.video_name,
        keyframe_path: `src/assets/${frame.keyframe_path}`,
        number: frame.keyframe,
        youtube: frame.youtube_url,
        similarity_score: frame.similarity_score,
      }))
    } catch (error) {
      alert('Lỗi khi gửi yêu cầu: ' + error.message)
      console.error(error)
    }
  },

  SearchL25: async (text, transcription = '', ocr = '') => {
    try {
      const t = (text ?? '').toString().trim();
      const tc = (transcription ?? '').toString().trim();
      const o = (ocr ?? '').toString().trim();

      if (!t && !tc && !o) return; // nothing to search
      const res = await axios.post(`http://${IPStore.getIP()}/quick-search-l25/`, {
        text: t || null,
        transcript: tc || null,
        ocr: o || null,
      })
      const mapped = res.data.rows.map(video => ({
        title: video.video_name,
        frames: video.keyframe_paths.map((path, idx) => ({
          image: `src/assets/${path}`,
          keyframe_path: path,
          number: video.keyframes[idx],
          youtube: video.youtube_links[idx],
        })),
        text: video.transcript,
      }))
      // Preserve context row at index 0 if present
      if (videos.value.length > 0 && videos.value[0].__isContext) {
        videos.value = [videos.value[0], ...mapped]
      } else {
        videos.value = mapped
      }
      similarFrames.value = res.data.similar_frames.map(frame => ({
        video_name: frame.video_name,
        keyframe_path: `src/assets/${frame.keyframe_path}`,
        number: frame.keyframe,
        youtube: frame.youtube_url,
        similarity_score: frame.similarity_score,
      }))
    } catch (error) {
      alert('Lỗi khi gửi yêu cầu: ' + error.message)
      console.error(error)
    }
  }, 

  // duplicate removed

  multiSearch: async (data) => {
    try {
      const res = await axios.post(`http://${IPStore.getIP()}/multi-keyframe-search/`, data)
      const mapped = res.data.rows.map(video => ({
        title: video.video_name,
        frames: video.keyframe_paths.map((path, idx) => ({
          image: `src/assets/${path}`,
          keyframe_path: path,
          number: video.keyframes[idx],
          youtube: video.youtube_links[idx],
        })),
        text: video.transcript,
      }))
      // Preserve context row at index 0 if present
      if (videos.value.length > 0 && videos.value[0].__isContext) {
        videos.value = [videos.value[0], ...mapped]
      } else {
        videos.value = mapped
      }
      similarFrames.value = res.data.similar_frames.map(frame => ({
        video_name: frame.video_name,
        keyframe_path: `src/assets/${frame.keyframe_path}`,
        number: frame.keyframe,
        youtube: frame.youtube_url,
        similarity_score: frame.similarity_score,
      }))
    } catch (error) {
      alert('Lỗi khi gửi yêu cầu: ' + error.message)
      console.error(error)
    }
  },

  // Fetch surrounding context frames for a given keyframe and append as a new video
  contextSequence: async (keyframePath) => {
    try {
      const res = await axios.post(`http://${IPStore.getIP()}/context-sequence/`, { keyframe_path: keyframePath });
      const ctx = res.data;

      const newVideo = {
        title: `${ctx.video_name}`,
        frames: ctx.frames.map(f => {
          const p = f.keyframe_path;
          const start = p.lastIndexOf('/') + 1;
          const end = p.lastIndexOf('.') > start ? p.lastIndexOf('.') : p.length;
          const numStr = p.substring(start, end);
          return {
            image: `src/assets/${p}`,
            keyframe_path: p,
            number: Number(numStr),
            youtube: f.youtube_url,
          }
        }),
        text: '', // no transcript for context sequence
        __isContext: true,
      };

      // Ensure a single fixed context row at index 0
      const rest = (videos.value || []).filter(v => !v.__isContext)
      videos.value = [newVideo, ...rest]
    } catch (error) {
      console.error('Error:', error.response ? error.response.data : error.message);
    }
  },

  loadAPI: async () => {
    try {
      const response = await axios.get(`${IPStore.getIP()}`);
      return response;
    } catch (error) {
      console.error('Error:', error.response ? error.response.data :
         error.message);
      return
    }
  },

  submit: async (data) => {
    try {
      const response = await axios.post(`http://${IPStore.getIP()}/submit/`, data);
      return response.data;
    } catch (error) {
      console.error('Error:', error.response ? error.response.data : error.message);
      return;
    }
  },

  // Query dạng 2 (Q&A): context + question là 2 trường tách biệt (frontend đã có tab
  // Q&A riêng nên người dùng tự nhập đúng 2 phần, không cần đoán từ 1 khối text gộp).
  // Ảnh dùng lại đúng keyframe_path do backend trả về (đã tồn tại sẵn dưới src/assets/,
  // không tự ghép từ frame_id để tránh sai định dạng/zero-padding tên file).
  qaSearch: async (context, question, numContextFrames = 1) => {
    try {
      const ctx = (context ?? '').toString().trim();
      const q = (question ?? '').toString().trim();
      if (!ctx || !q) return;
      const res = await axios.post(`http://${IPStore.getIP()}/qa-search/`, {
        context: ctx,
        question: q,
        num_context_frames: numContextFrames,
      })
      if (res.data.error) {
        alert('Lỗi Q&A: ' + res.data.error)
        return
      }
      videos.value = [{
        title: res.data.video_name,
        frames: [{
          image: `src/assets/${res.data.keyframe_path}`,
          keyframe_path: res.data.keyframe_path,
          number: res.data.frame_id,
          youtube: null,
        }],
        text: `Câu hỏi: ${res.data.question_vi}\nTrả lời: ${res.data.answer}`,
      }]
      similarFrames.value = []
      return res.data
    } catch (error) {
      alert('Lỗi khi gửi yêu cầu Q&A: ' + error.message)
      console.error(error)
    }
  },

  // Query dạng 3 (TRAKE): 1 khối text (context + "E1: ..." .. "En: ...") -> video + N
  // frame theo đúng thứ tự sự kiện. Ảnh TRAKE được sinh động (dense re-sample) nên KHÔNG
  // dùng quy ước "src/assets/..." (chỉ áp dụng cho keyframe tĩnh đã copy sẵn) -- load
  // trực tiếp từ route static /dense-frames/ mới thêm ở backend.
  trakeSearch: async (queryText) => {
    try {
      const q = (queryText ?? '').toString().trim();
      if (!q) return;
      const res = await axios.post(`http://${IPStore.getIP()}/trake-search/`, {
        query_text: q,
      })
      if (res.data.error) {
        alert('Lỗi TRAKE: ' + res.data.error)
        return
      }
      videos.value = [{
        title: res.data.video_name,
        frames: res.data.frame_ids.map((fid, idx) => ({
          image: `http://${IPStore.getIP()}/dense-frames/${res.data.video_name}/${fid}.jpg`,
          keyframe_path: res.data.frame_paths[idx],
          number: fid,
          youtube: null,
          eventLabel: `E${idx + 1}`,
        })),
        text: `${res.data.num_events} sự kiện · điểm định vị thô: ${Number(res.data.coarse_score).toFixed(3)}`,
      }]
      similarFrames.value = []
      return res.data
    } catch (error) {
      alert('Lỗi khi gửi yêu cầu TRAKE: ' + error.message)
      console.error(error)
    }
  },

}
// async function testApi(text) {
//   try {
//     const response = await axios.post(API_URL, {
//       text: text
//     });

//     console.log('\nAPI Response:');
//     console.log('English Translation:', response.data.translated_english_text);
//     console.log(`Found ${response.data.similar_frames.length} results:`);

//     // Hiển thị 5 kết quả đầu tiên
//     response.data.similar_frames.slice(0, 5).forEach((frame, index) => {
//       console.log(`\nResult ${index + 1}:`);
//       console.log('Video Name:', frame.video_name);
//       console.log('Keyframe Path:', frame.keyframe_path);
//       console.log('Similarity Score:', frame.similarity_score.toFixed(4));
//     });

//   } catch (error) {
//     console.error('\nError:', error.response ? error.response.data : error.message);
//   }
// }

// function askQuestion() {
//   rl.question('\nEnter Vietnamese text (or press Enter to exit): ', async (input) => {
//     if (input.trim() === '') {
//       console.log('Exiting...');
//       rl.close();
//       return;
//     }

//     await testApi(input);
//     askQuestion(); // Lặp lại hỏi input
//   });
// }

// console.log('API Tester for Video Search');
// console.log('============================');
// console.log('Note: Enter Vietnamese text to search similar video frames');
// console.log('Press Enter with empty input to exit\n');

// // Bắt đầu chương trình
// askQuestion();