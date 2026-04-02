import { create } from 'zustand'
import type { Voice } from '../types'
import { apiFetch } from '../lib/api'

interface VoiceState {
  voices: Voice[]
  loading: boolean
  fetchVoices: () => Promise<void>
  deleteVoice: (id: string) => Promise<void>
  toggleFavorite: (id: string) => Promise<void>
}

export const useVoiceStore = create<VoiceState>((set, get) => ({
  voices: [],
  loading: false,

  fetchVoices: async () => {
    set({ loading: true })
    try {
      const voices = await apiFetch<Voice[]>('/voices')
      set({ voices })
    } catch {
      // ignore
    } finally {
      set({ loading: false })
    }
  },

  deleteVoice: async (id) => {
    await apiFetch(`/voices/${id}`, { method: 'DELETE' })
    set({ voices: get().voices.filter((v) => v.id !== id) })
  },

  toggleFavorite: async (id) => {
    const voice = get().voices.find((v) => v.id === id)
    if (!voice) return
    await apiFetch(`/voices/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_favorite: !voice.is_favorite }),
    })
    set({
      voices: get().voices.map((v) =>
        v.id === id ? { ...v, is_favorite: !v.is_favorite } : v,
      ),
    })
  },
}))
