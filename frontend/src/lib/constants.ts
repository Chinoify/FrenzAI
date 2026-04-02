import type { TTSParams } from '../types'

export const DEFAULT_PARAMS: TTSParams = {
  speed: 1.0,
  stability: 0.7,
  clarity: 0.8,
  steps: 4,
}

export const MAX_TEXT_LENGTH = 50000

export const LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'zh', name: 'Chinese' },
  { code: 'ja', name: 'Japanese' },
  { code: 'ko', name: 'Korean' },
  { code: 'fr', name: 'French' },
  { code: 'de', name: 'German' },
  { code: 'es', name: 'Spanish' },
  { code: 'pt', name: 'Portuguese' },
  { code: 'ru', name: 'Russian' },
  { code: 'ar', name: 'Arabic' },
]
