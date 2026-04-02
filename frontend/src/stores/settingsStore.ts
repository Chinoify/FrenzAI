import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { apiFetch } from '../lib/api'

export interface AppSettings {
  // General
  theme: 'dark' | 'light' | 'system'
  font_size: 'small' | 'medium' | 'large'
  compact_mode: boolean
  auto_save_interval: number
  startup_page: string
  notification_generation_complete: boolean
  notification_errors: boolean
  notification_sound: boolean
  notification_volume: number

  // Audio Engine
  active_tts_model: string
  generation_quality: string
  default_temperature: number
  default_seed: number | null
  random_seed: boolean
  max_tokens_per_chunk: number
  batch_size: number
  fallback_model: string
  active_stt_model: string
  stt_language: string
  stt_word_timestamps: boolean
  stt_vad_filter: boolean
  stt_beam_size: number

  // Voice & Cloning
  default_stability: number
  default_similarity: number
  default_style: number
  default_speed: number
  min_reference_length: number
  auto_enhance_reference: boolean

  // ACX
  acx_rms_target: number
  acx_peak_max: number
  acx_noise_max: number
  acx_bitrate: string
  noise_scrubber_enabled: boolean
  noise_scrubber_strength: number
  warmth_eq_enabled: boolean
  warmth_low_shelf_db: number
  warmth_high_shelf_db: number
  compression_enabled: boolean
  compression_threshold: number
  reverb_enabled: boolean
  reverb_room_size: number
  reverb_wet_level: number
  humanizer_enabled: boolean
  humanizer_speed_variation: number
  humanizer_volume_variation: number
  breath_enabled: boolean
  breath_threshold_words: number
  max_parallel_chapters: number

  // GPU
  vram_warn_threshold: number
  vram_critical_threshold: number
  auto_flush_vram: boolean
  compute_precision: string
  force_cpu: boolean
  parallel_threads: number
  show_vram_in_header: boolean
  show_cpu_in_header: boolean

  // Accessibility
  reduce_motion: boolean
  high_contrast: boolean
  text_scaling: number
  waveform_style: string
  color_theme: string

  // Developer
  developer_mode: boolean
  log_level: string

  [key: string]: unknown
}

const DEFAULT_SETTINGS: AppSettings = {
  theme: 'dark',
  font_size: 'medium',
  compact_mode: false,
  auto_save_interval: 60,
  startup_page: '/',
  notification_generation_complete: true,
  notification_errors: true,
  notification_sound: true,
  notification_volume: 80,
  active_tts_model: 'kokoro',
  generation_quality: 'standard',
  default_temperature: 0.7,
  default_seed: null,
  random_seed: true,
  max_tokens_per_chunk: 300,
  batch_size: 3,
  fallback_model: 'builtin',
  active_stt_model: 'base',
  stt_language: 'auto',
  stt_word_timestamps: true,
  stt_vad_filter: true,
  stt_beam_size: 5,
  default_stability: 70,
  default_similarity: 80,
  default_style: 50,
  default_speed: 1.0,
  min_reference_length: 30,
  auto_enhance_reference: true,
  acx_rms_target: -20.0,
  acx_peak_max: -3.0,
  acx_noise_max: -60.0,
  acx_bitrate: '192k',
  noise_scrubber_enabled: true,
  noise_scrubber_strength: 75,
  warmth_eq_enabled: true,
  warmth_low_shelf_db: 1.5,
  warmth_high_shelf_db: -2.0,
  compression_enabled: true,
  compression_threshold: -20,
  reverb_enabled: true,
  reverb_room_size: 10,
  reverb_wet_level: 5,
  humanizer_enabled: true,
  humanizer_speed_variation: 3,
  humanizer_volume_variation: 1.5,
  breath_enabled: true,
  breath_threshold_words: 15,
  max_parallel_chapters: 2,
  vram_warn_threshold: 85,
  vram_critical_threshold: 92,
  auto_flush_vram: true,
  compute_precision: 'float16',
  force_cpu: false,
  parallel_threads: 3,
  show_vram_in_header: true,
  show_cpu_in_header: false,
  reduce_motion: false,
  high_contrast: false,
  text_scaling: 100,
  waveform_style: 'bars',
  color_theme: 'purple',
  developer_mode: false,
  log_level: 'INFO',
}

let syncTimer: ReturnType<typeof setTimeout> | null = null

interface SettingsState {
  settings: AppSettings
  loaded: boolean
  updateSetting: (key: string, value: unknown) => void
  updateSettings: (updates: Partial<AppSettings>) => void
  resetAll: () => void
  resetCategory: (keys: string[]) => void
  loadFromServer: () => Promise<void>
  exportSettings: () => string
  importSettings: (json: string) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set, get) => ({
      settings: { ...DEFAULT_SETTINGS },
      loaded: false,

      updateSetting: (key, value) => {
        set((s) => ({
          settings: { ...s.settings, [key]: value },
        }))
        // Debounced sync to backend
        if (syncTimer) clearTimeout(syncTimer)
        syncTimer = setTimeout(() => {
          apiFetch('/settings/save', {
            method: 'POST',
            body: JSON.stringify({ [key]: value }),
          }).catch(() => {})
        }, 500)
      },

      updateSettings: (updates) => {
        set((s) => ({
          settings: { ...s.settings, ...updates },
        }))
        if (syncTimer) clearTimeout(syncTimer)
        syncTimer = setTimeout(() => {
          apiFetch('/settings/save', {
            method: 'POST',
            body: JSON.stringify(updates),
          }).catch(() => {})
        }, 500)
      },

      resetAll: () => {
        set({ settings: { ...DEFAULT_SETTINGS } })
        apiFetch('/settings/reset', { method: 'POST' }).catch(() => {})
      },

      resetCategory: (keys) => {
        const reset: Partial<AppSettings> = {}
        for (const key of keys) {
          if (key in DEFAULT_SETTINGS) {
            (reset as Record<string, unknown>)[key] = (DEFAULT_SETTINGS as Record<string, unknown>)[key]
          }
        }
        get().updateSettings(reset)
      },

      loadFromServer: async () => {
        try {
          const data = await apiFetch<AppSettings>('/settings')
          set({ settings: { ...DEFAULT_SETTINGS, ...data }, loaded: true })
        } catch {
          set({ loaded: true })
        }
      },

      exportSettings: () => {
        return JSON.stringify(get().settings, null, 2)
      },

      importSettings: (json) => {
        try {
          const imported = JSON.parse(json)
          set({ settings: { ...DEFAULT_SETTINGS, ...imported } })
          apiFetch('/settings/save', {
            method: 'POST',
            body: JSON.stringify(imported),
          }).catch(() => {})
        } catch {
          throw new Error('Invalid settings JSON')
        }
      },
    }),
    {
      name: 'frenzai-settings',
      partialize: (state) => ({ settings: state.settings }),
    }
  )
)
