import { create } from 'zustand'
import type { GPUInfo, ModelInfo } from '../types'
import { apiFetch } from '../lib/api'

interface AppState {
  gpu: GPUInfo | null
  device: string
  activeModel: string | null
  models: ModelInfo[]
  voicesCount: number
  version: string
  sidebarExpanded: boolean

  setSidebarExpanded: (expanded: boolean) => void
  fetchHealth: () => Promise<void>
  fetchModels: () => Promise<void>
}

export const useAppStore = create<AppState>((set) => ({
  gpu: null,
  device: 'cpu',
  activeModel: null,
  models: [],
  voicesCount: 0,
  version: '',
  sidebarExpanded: true,

  setSidebarExpanded: (expanded) => set({ sidebarExpanded: expanded }),

  fetchHealth: async () => {
    try {
      const data = await apiFetch<{
        gpu: GPUInfo
        device: string
        active_model: string | null
        voices_count: number
        version: string
      }>('/health')
      set({
        gpu: data.gpu,
        device: data.device,
        activeModel: data.active_model,
        voicesCount: data.voices_count,
        version: data.version,
      })
    } catch {
      // Backend not ready yet
    }
  },

  fetchModels: async () => {
    try {
      const data = await apiFetch<{ models: ModelInfo[]; active_model: string | null }>('/models')
      set({ models: data.models, activeModel: data.active_model })
    } catch {
      // ignore
    }
  },
}))
