import { create } from 'zustand'

interface GenerationState {
  isGenerating: boolean
  progress: {
    currentChunk: number
    totalChunks: number
    percent: number
    message: string
  } | null
  lastAudioUrl: string | null
  lastTranscript: string | null

  setGenerating: (generating: boolean) => void
  setProgress: (progress: GenerationState['progress']) => void
  setLastAudio: (url: string | null) => void
  setLastTranscript: (text: string | null) => void
  reset: () => void
}

export const useGenerationStore = create<GenerationState>((set) => ({
  isGenerating: false,
  progress: null,
  lastAudioUrl: null,
  lastTranscript: null,

  setGenerating: (generating) => set({ isGenerating: generating }),
  setProgress: (progress) => set({ progress }),
  setLastAudio: (url) => set({ lastAudioUrl: url }),
  setLastTranscript: (text) => set({ lastTranscript: text }),
  reset: () => set({
    isGenerating: false,
    progress: null,
    lastAudioUrl: null,
    lastTranscript: null,
  }),
}))
