import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { TTSGenerateResponse, TTSParams } from '../types'
import { DEFAULT_PARAMS } from '../lib/constants'
import { apiFetch } from '../lib/api'

interface StudioState {
  text: string
  selectedVoiceId: string | null
  selectedModel: string
  language: string
  params: TTSParams
  generating: boolean
  progress: string
  output: TTSGenerateResponse | null
  error: string | null

  setText: (text: string) => void
  setSelectedVoiceId: (id: string | null) => void
  setSelectedModel: (model: string) => void
  setLanguage: (lang: string) => void
  setParam: (key: keyof TTSParams, value: number) => void
  generate: () => Promise<void>
  clear: () => void
}

export const useStudioStore = create<StudioState>()(
  persist(
    (set, get) => ({
      text: '',
      selectedVoiceId: null,
      selectedModel: 'kokoro',
      language: 'en',
      params: { ...DEFAULT_PARAMS },
      generating: false,
      progress: '',
      output: null,
      error: null,

      setText: (text) => set({ text }),
      setSelectedVoiceId: (id) => set({ selectedVoiceId: id }),
      setSelectedModel: (model) => set({ selectedModel: model }),
      setLanguage: (lang) => set({ language: lang }),
      setParam: (key, value) =>
        set((s) => ({ params: { ...s.params, [key]: value } })),

      generate: async () => {
        const { text, selectedModel, selectedVoiceId, language, params } = get()
        if (!text.trim()) return

        const payload = {
          text: text.trim(),
          model: selectedModel,
          voice_id: selectedVoiceId || undefined,
          language,
          ...params,
        }
        console.log('[TTS Generate]', { model: selectedModel, voice_id: selectedVoiceId })

        set({ generating: true, error: null, progress: 'Generating...' })
        try {
          const result = await apiFetch<TTSGenerateResponse>('/tts/generate', {
            method: 'POST',
            body: JSON.stringify(payload),
          })
          set({ output: result, progress: `Generated in ${result.generation_time}s` })
        } catch (e) {
          set({ error: e instanceof Error ? e.message : 'Generation failed' })
        } finally {
          set({ generating: false })
        }
      },

      clear: () => set({ text: '', output: null, error: null, progress: '' }),
    }),
    {
      name: 'frenzai-studio',
      partialize: (state) => ({
        text: state.text,
        selectedVoiceId: state.selectedVoiceId,
        selectedModel: state.selectedModel,
        language: state.language,
        params: state.params,
        output: state.output,
      }),
    }
  )
)
