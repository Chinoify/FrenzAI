export interface GPUInfo {
  available: boolean
  name: string | null
  vram_total_mb: number | null
  vram_used_mb: number | null
  vram_free_mb: number | null
}

export interface HealthResponse {
  status: string
  version: string
  gpu: GPUInfo
  active_model: string | null
  voices_count: number
  device: string
}

export interface Voice {
  id: string
  name: string
  engine: string
  language: string
  tags: string[]
  notes: string
  quality_score: number
  use_count: number
  is_favorite: boolean
  sample_url: string | null
  created_at: string
}

export interface TTSGenerateRequest {
  text: string
  model: string
  voice_id?: string
  language: string
  speed: number
  stability: number
  clarity: number
  steps: number
}

export interface TTSGenerateResponse {
  audio_url: string
  duration: number
  generation_time: number
}

export interface ModelInfo {
  name: string
  display_name: string
  description: string
  languages: string[]
  vram_required_mb: number
  model_size_mb: number
  license: string
  is_downloaded: boolean
  is_loaded: boolean
}

export interface ModelListResponse {
  models: ModelInfo[]
  active_model: string | null
}

export interface Project {
  id: string
  name: string
  text: string
  voice_id: string | null
  model: string | null
  language: string
  params: Record<string, unknown>
  segments: SegmentInfo[]
  merged_audio_path: string | null
  created_at: string
  updated_at: string | null
}

export interface SegmentInfo {
  index: number
  text: string
  audio_path: string | null
  duration: number | null
}

// --- Audiobook ---
export interface Chapter {
  id: string
  index: number
  title: string
  text: string
  voice_id: string | null
  model: string | null
  status: 'pending' | 'generating' | 'completed' | 'error'
  audio_url: string | null
  duration: number | null
}

export interface ProjectDetail {
  id: string
  name: string
  source_type: string
  source_filename: string | null
  default_voice_id: string | null
  default_model: string | null
  total_duration: number | null
  status: string
  language: string
  chapters: Chapter[]
  merged_audio_path: string | null
  created_at: string
  updated_at: string | null
}

export interface HistoryEntry {
  id: number
  text_preview: string | null
  voice_name: string | null
  model: string | null
  audio_url: string | null
  duration_seconds: number | null
  created_at: string
}

export interface TTSParams {
  speed: number
  stability: number
  clarity: number
  steps: number
}
