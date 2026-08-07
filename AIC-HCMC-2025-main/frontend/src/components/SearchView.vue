<script setup>
import { useSelectedFramesStore } from '@/stores/selectedFrames'
import { useIPStore } from '@/stores/IP'
// import { similarFrames } from './TopContentView.vue'
// import { toRaw } from 'vue';
import { API } from '@/api/retrieval'
import { ref } from 'vue'
import { defineExpose } from 'vue'
import axios from 'axios'
import { useSearchQueryStore } from '@/stores/searchQuery'

const ipStore = useIPStore()
const searchQuery = useSearchQueryStore()
const text = ref('')
const translated = ref('')
const nextScene = ref('')
const nextSceneTranslated = ref('')

// New fields for quick search payload
const transcription = ref('')
const ocr = ref('')

const QuestionID = ref(1)
const frameStore = useSelectedFramesStore()
const showNumberInputs = ref(false);
const qaInput = ref(false);
const qaContent = ref('');

const numberOfInputs = ref(0);
const confirmedInputs = ref(0);
const inputValues = ref([]);

async function validateInputs() {
  if (!QuestionID.value || QuestionID.value < 1) {
    alert("Please enter a valid Question ID");
    return false;
  }

  if (qaInput.value && showNumberInputs.value) {
    alert("Only one of QA or Manual Input can be selected");
    return false;
  }

  if (showNumberInputs.value) {
    const seen = new Set();
    for (let i = 0; i < confirmedInputs.value; i++) {
      const raw = (inputValues.value[i] ?? '').trim();
      if (!raw || !/^[^,]+,\d+(?:\.\d+)?$/.test(raw)) {
        alert(`Input ${i + 1} is invalid. Please enter in the format "video,frame_id" (frame_id can include decimals).`);
        return false;
      }
      const [v] = raw.split(',');
      const firstVideo = inputValues.value[0].split(',')[0];
      if (v !== firstVideo) {
        alert('All inputs must belong to the same video.');
        return false;
      }
      if (seen.has(raw)) {
        alert(`Input ${i + 1} is duplicated. Please enter unique values.`);
        return false;
      }
      seen.add(raw);
    }
  }
  return true;
}



function fillFrames() {
  let result = [...frameStore.selectedFrames || []];
  // if (result.length < 100) {
  //   if (similarFrames.value && Array.isArray(similarFrames.value)) {
  //     const existing = new Set(result.map(f => `${f.vIdx},${f.fIdx}`));
  //     const similar = similarFrames.value.map(item => toRaw(item));

  //     for (const sim of similar) {
  //       const key = `${sim.video_name},${sim.number}`;
  //       if (!existing.has(key)) {
  //         result.push({
  //           vIdx: sim.video_name,
  //           fIdx: sim.number,
  //           keyframe_paths: sim.keyframe_path
  //         });
  //         existing.add(key);
  //         if (result.length >= 100) break;
  //       }
  //     }
  //   }
  // }
  return result;
}

async function handleSelectClick() {
  if (!await validateInputs()) return;

  let data = {
    question_number: QuestionID.value || 0
  };

  if (qaInput.value) {
    let res_frames = fillFrames();
    // mode 2: use selected frames + text as QA content
    data = {
      ...data,
      mode: 2,
      selected_frames: res_frames.map(f => ({
        video_name: String(f.vIdx),  
        keyframe_idx: Number(f.fIdx)  
      })),
      answer: qaContent.value ?? ""   
    };
  } else if (showNumberInputs.value) {
    // mode 3: manual input "video,frame_id"
    data = {
      ...data,
      mode: 3,
      selected_frames: inputValues.value.map((value) => {
        const [videoRaw, frameIdRaw] = value.split(',');
        return {
          video_name: videoRaw.trim(),
          keyframe_idx: Number(frameIdRaw.trim())
        };
      }),
      answer: ""
    };
  } else {
    let res_frames = fillFrames();
    // mode 1: use selected frames, answer can be taken from "Base query" input (or empty)
    data = {
      ...data,
      mode: 1,
      selected_frames: res_frames.map(f => ({
        video_name: String(f.vIdx),
        keyframe_idx: Number(f.fIdx)
      })),
      answer: (text.value ?? "").toString()
    };
  }

  try {
    if (data.selected_frames.length !== 1 && data.mode !== 3) {
      alert(data.selected_frames.length);
      alert('Please select only one frame');
      frameStore.clear();
      return;
    }
    console.log(data)
    const response = await API.submit(data);
    alert(response.result.description);
    frameStore.clear();
  } catch (e) {
    alert('Submit error: ' + (e?.message || 'Unknown'));
    console.error(e);
    frameStore.clear();
  }
}


async function translateText() {
  if (text.value.trim() === '') {
    translated.value = ''
    return
  }

  try {
    const res = await axios.post(`http://${ipStore.getIP()}/translate/`, { text: text.value })
    translated.value = res.data.english_text
  } catch (error) {
    translated.value = 'Translation error'
    console.error(error)
  }
}

async function translateNextScene() {
  if ((nextScene.value ?? '').trim() === '') {
    nextSceneTranslated.value = ''
    return
  }

  try {
    const res = await axios.post(`http://${ipStore.getIP()}/translate/`, { text: nextScene.value })
    nextSceneTranslated.value = res.data.english_text
  } catch (error) {
    nextSceneTranslated.value = 'Translation error'
    console.error(error)
  }
}

async function Search() {
  try {
  await translateText()
  // sync transcription query for highlighting
  searchQuery.setTranscription(transcription.value)
  await API.quickSearch(translated.value, transcription.value, ocr.value)
  resetScrollPositions()
  } catch (error) {
    console.error('Error during search:', error)
  }
}

async function SearchL26() {
  try {
  await translateText()
  // sync transcription query for highlighting
  searchQuery.setTranscription(transcription.value)
  await API.SearchL26(translated.value, transcription.value, ocr.value)
  resetScrollPositions()
  } catch (error) {
    console.error('Error during search L26:', error)
  }
}

async function SearchL25() {
  try {
  await translateText()
  // sync transcription query for highlighting
  searchQuery.setTranscription(transcription.value)
  await API.SearchL25(translated.value, transcription.value, ocr.value)
  resetScrollPositions()
  } catch (error) {
    console.error('Error during search L25:', error)
  }
}

// expose Search to parent components so they can trigger it
defineExpose({ Search })

async function MultiSearch() {
  await translateText()
  let data = {
    keyframe_paths: frameStore.selectedFrames.map(f=> (f.keyframe_paths)),

    text: translated.value ?? ""
  };

  try {
  searchQuery.setTranscription(transcription.value)
    await API.multiSearch(data)
    resetScrollPositions()
  } catch (error) {
    console.error('Error during multi-search:', error)
  }
}

function resetScrollPositions() {
  try {
    // Reset vertical scroll of the content area
    const content = document.querySelector('.main-content')
    if (content) {
      content.scrollTop = 0
    } else {
      // Fallback to document if needed
      window.scrollTo({ top: 0, behavior: 'auto' })
    }

    // Reset horizontal scroll of each frames scroller
    const containers = document.querySelectorAll('.video-frames')
    containers.forEach(container => {
      container.scrollLeft = 0
    })
  } catch (e) {
    // non-fatal
    console.warn('Failed to reset scroll positions', e)
  }
}

async function TemporalSearch() {
  try {
  await translateText()
  await translateNextScene()
  searchQuery.setTranscription(transcription.value)
    await API.temporalSearch(translated.value, nextSceneTranslated.value)
    resetScrollPositions()
  } catch (e) {
    console.error('Error during temporal search:', e)
  }
}

function showLastType() {
  if (!showNumberInputs.value) {
    confirmedInputs.value = 0;
    inputValues.value = [];
    numberOfInputs.value = 0;
  }
}

function confirmNumberInputs() {
  if (numberOfInputs.value > 0) {
    confirmedInputs.value = numberOfInputs.value;
    inputValues.value = Array.from({ length: confirmedInputs.value }, (_, i) => inputValues.value[i] || '');
  }
}

</script>
<template>
    <div class="sidebar">
      <div class="input-section">
        <h3>Base query</h3>
  <textarea v-model="text" class="input-field" placeholder="Enter content..." @keydown.enter.prevent="Search"></textarea>
        <p>English translation: {{ translated }}</p>
      </div>

      <!-- <div class="input-section">
        <div class="checkbox-container">
          <label for="next-scene">Next scene</label>
        </div>
  <textarea v-model="nextScene" class="input-field" placeholder="Enter content..." @keydown.enter.prevent="Search"></textarea>
        <p>English translation: {{ nextSceneTranslated }}</p> -->
  <!-- <button class="search-button" @click="TemporalSearch">Temporal Search</button> -->
      <!-- </div> -->
       <button class="search-button" @click="SearchL26" style="margin-right:10px">Search L26</button>
       <button class="search-button" @click="SearchL25">Search L25</button>

      <div class="input-section">
        <div class="checkbox-container">
          <label for="transcription">Transcription</label>
        </div>
  <textarea v-model="transcription" class="input-field" placeholder="Enter content..." @keydown.enter.prevent="Search"></textarea>
      </div>

      <div class="input-section">
        <div class="checkbox-container">
          <label for="ocr">OCR</label>
        </div>
  <textarea v-model="ocr" class="input-field" placeholder="Enter content..." @keydown.enter.prevent="Search"></textarea>
      </div>

      <button class="search-button" @click=Search>Search</button>
      <button class="search-button" style="margin-left:10px" @click=MultiSearch>MultiSearch</button>

      <div class="rowww">
        <div class="question-id">
          <h4>Question ID</h4>
            <input
            type="number"
            v-model.number="QuestionID"
            min="1"
            style="
              width: 100px;
              text-align: center;
              display: flex;
              align-items: center;
              background-color: #333;
              border: 1px solid #444;
              border-radius: 4px;
              color: #fff;
              padding: 8px;
            "
            placeholder="ID"
            />
        </div>

        <div class="qa-checkbox">
          <h4>
            <input type="checkbox" id="qa"  v-model="qaInput" />
            <label for="qa">QA</label>
          </h4>
            <textarea
              v-model="qaContent"
              style="
                min-height: auto;
                background-color: #333;
                border: 1px solid #444;
                border-radius: 4px;
                color: #fff;
              "
              placeholder="Enter content..."
            ></textarea>
        </div>
      </div>
      <div class="input-section">
        <div class="checkbox-container">
          <input type="checkbox" id="show-number-inputs" v-model="showNumberInputs" @click="showLastType"/>
          <label for="show-number-inputs">Manual input</label>
        </div>
        <div v-if="showNumberInputs" style="margin-top: 10px; ">
          <input
            type="number"
            min="1"
            v-model.number="numberOfInputs"
            placeholder="Enter number of inputs"
            style="width: 120px; margin-right: 10px; color:#333"
          />
          <button @click="confirmNumberInputs" style="padding: 5px 10px;">Confirm</button>
        </div>
        <div v-if="confirmedInputs > 0" style="margin-top: 10px;">
          <div v-for="n in confirmedInputs" :key="n" style="margin-bottom: 5px;">
            <input
              type="text"
              :placeholder="`Input ${n}`"
              class="input-field"
              style="min-height: auto; height: 32px;"
              v-model="inputValues[n - 1]"
              @focus="() => {
                inputValues[n - 1] = frameStore.selectedFrames[0] ? `${frameStore.selectedFrames[0].vIdx},${frameStore.selectedFrames[0].fIdx}` : inputValues[n - 1];
                frameStore.clear();
              }"
            />
          </div>
        </div>
      </div>
      <button class="select-button"  @click=handleSelectClick>Submit</button>
    </div>
</template>


<style scoped>
    .sidebar {
        width: 25%;
        background-color: #222;
        color: #fff;
        padding: 20px;
        overflow-y: auto;
        scrollbar-width: thin;
        scrollbar-color: #888 transparent;
    }


    .input-section {
        width: 100%;
        margin-bottom: 10px;
    }

    .input-section h3 {
        margin-top: 0;
        margin-bottom: 10px;
        color: #ccc;
        font-weight: normal;
        font-size: 16px;
    }

    .input-field {
        width: 100%;
        padding: 10px;
        min-height: 100px;
        background-color: #333;
        border: 1px solid #444;
        border-radius: 4px;
        color: #fff;
        margin-top: 5px;
    }

    .checkbox-container {
        display: flex;
        align-items: center;
        margin-bottom: 10px;
    }

    .checkbox-container input {
        margin-right: 10px;
    }

    .search-button {
        padding: 10px 20px;
        background-color: #555;
        color: #fff;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        margin-top: 10px;
    }

    .search-button:hover {
        background-color: #666;
    }


    .question-id {
        display: flex;
        align-items: center;
        flex-direction: column;
        margin-top: 20px;
    }

    .question-id select {
        padding: 8px;
        margin-right: 10px;
        background-color: #333;
        color: #fff;
        border: 1px solid #444;
        width: 100px;
    }

    .select-button {
        padding: 8px 15px;
        background-color: #19d19a;
        color: #000000;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }
    .select-button:hover {
        background-color: #1abc9c;
    }
    .qa-checkbox {
        margin-left: 20px;
        margin-top: 20px;
        display: flex;
        flex-direction: column;
    }

    .qa-checkbox input {
        margin-right: 5px;
    }
    .rowww {
        display: flex;
        align-items: center;
        margin-top: 20px;
        margin-bottom: 20px;
    }
</style>
