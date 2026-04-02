import { create } from 'zustand'
import { apiFetch } from '../lib/api'

interface SystemState {
  vram: { used_gb: number; total_gb: number; percent: number; gpu_name: string }
  cpu: number
  ram: { used_gb: number; total_gb: number }
  isBackendConnected: boolean
  activeModel: string | null
  uptime: number
  polling: boolean

  pollSystemStatus: () => Promise<void>
  startPolling: () => void
  stopPolling: () => void
}

let pollInterval: ReturnType<typeof setInterval> | null = null

export const useSystemStore = create<SystemState>((set, get) => ({
  vram: { used_gb: 0, total_gb: 0, percent: 0, gpu_name: 'N/A' },
  cpu: 0,
  ram: { used_gb: 0, total_gb: 0 },
  isBackendConnected: false,
  activeModel: null,
  uptime: 0,
  polling: false,

  pollSystemStatus: async () => {
    try {
      const data = await apiFetch<{
        vram_used_gb: number
        vram_total_gb: number
        cpu_percent: number
        ram_used_gb: number
        ram_total_gb: number
        active_model: string | null
        uptime_sec: number
      }>('/system/status')

      set({
        vram: {
          used_gb: data.vram_used_gb,
          total_gb: data.vram_total_gb,
          percent: data.vram_total_gb > 0 ? Math.round(data.vram_used_gb / data.vram_total_gb * 100) : 0,
          gpu_name: 'GPU',
        },
        cpu: data.cpu_percent,
        ram: { used_gb: data.ram_used_gb, total_gb: data.ram_total_gb },
        isBackendConnected: true,
        activeModel: data.active_model,
        uptime: data.uptime_sec,
      })
    } catch {
      set({ isBackendConnected: false })
    }
  },

  startPolling: () => {
    if (get().polling) return
    set({ polling: true })
    get().pollSystemStatus()
    pollInterval = setInterval(() => get().pollSystemStatus(), 3000)
  },

  stopPolling: () => {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
    set({ polling: false })
  },
}))
