import { useState, useRef, useCallback, useEffect } from 'react'
import {
  Upload, Check, Loader2, FolderOpen, Play, Pause, Trash2,
  ChevronRight, Mic, Settings2
} from 'lucide-react'
import { apiFetch, apiUpload, audioUrl, BACKEND_URL } from '../lib/api'

interface StagedFile {
  stage_id: string
  filename: string
  ext: string
  size: number
  duration: number | null
  quality_score?: number
  gender?: string
  audio_url: string
  // Local UI state
  name: string
  status: 'ready' | 'adding' | 'done' | 'error'
  error?: string
  voice_id?: string
}

const STEPS = [
  { n: 1, label: 'Import' },
  { n: 2, label: 'Review' },
  { n: 3, label: 'Configure' },
  { n: 4, label: 'Done' },
]

const ENGINES = [
  { value: 'chatterbox', label: 'Chatterbox (Best for cloning)' },
  { value: 'f5tts', label: 'F5-TTS (Voice cloning)' },
  { value: 'qwen3tts', label: 'Qwen3-TTS (Multilingual)' },
  { value: 'fishspeech', label: 'Fish Speech (Multilingual)' },
  { value: 'kokoro', label: 'Kokoro' },
]

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'en-gb', label: 'British English' },
  { value: 'de', label: 'German' },
  { value: 'fr', label: 'French' },
  { value: 'es', label: 'Spanish' },
  { value: 'it', label: 'Italian' },
  { value: 'pt', label: 'Portuguese' },
  { value: 'ja', label: 'Japanese' },
  { value: 'zh', label: 'Chinese' },
  { value: 'ko', label: 'Korean' },
  { value: 'hi', label: 'Hindi' },
]

export default function CloneVoice() {
  const [step, setStep] = useState(1)
  const [files, setFiles] = useState<StagedFile[]>([])
  const [engine, setEngine] = useState('chatterbox')
  const [language, setLanguage] = useState('en')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState('')
  const [importResult, setImportResult] = useState<any>(null)
  const [importing, setImporting] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [playingId, setPlayingId] = useState<string | null>(null)
  const audioRefs = useRef<Record<string, HTMLAudioElement>>({})
  const fileRef = useRef<HTMLInputElement>(null)

  // Load staged files from backend on mount (persists across navigation)
  useEffect(() => {
    loadStaged()
  }, [])

  const loadStaged = async () => {
    try {
      const staged = await apiFetch<any[]>('/clone/staged')
      if (staged.length > 0) {
        setFiles(staged.map((s) => ({
          ...s,
          name: autoVoiceName(s.gender),
          status: 'ready' as const,
        })))
      }
    } catch {
      // Ignore — backend might not be running
    }
  }

  // Counter for auto-naming
  const nextVoiceNumber = useRef(1)

  const autoVoiceName = (gender?: string) => {
    const n = nextVoiceNumber.current++
    if (gender && gender !== 'Unknown') {
      return `${gender} Voice ${n}`
    }
    return `Voice ${n}`
  }

  // Upload files to backend staging (persists on disk)
  const addFiles = useCallback(async (fileList: FileList | File[]) => {
    setUploading(true)
    setError('')
    const arr = Array.from(fileList)

    for (const f of arr) {
      try {
        const form = new FormData()
        form.append('audio', f, f.name)
        const result = await apiUpload<any>('/clone/stage', form)
        const staged: StagedFile = {
          stage_id: result.stage_id,
          filename: result.filename,
          ext: result.ext,
          size: result.size,
          duration: result.duration,
          gender: result.gender,
          audio_url: result.audio_url,
          name: autoVoiceName(result.gender),
          status: 'ready',
        }
        setFiles((prev) => [...prev, staged])
      } catch (e) {
        setError(e instanceof Error ? e.message : `Failed to upload ${f.name}`)
      }
    }
    setUploading(false)
  }, [])

  const removeFile = async (stageId: string) => {
    try {
      await apiFetch(`/clone/staged/${stageId}`, { method: 'DELETE' })
    } catch { /* ignore */ }
    setFiles((prev) => prev.filter((f) => f.stage_id !== stageId))
  }

  const updateFileName = (stageId: string, name: string) => {
    setFiles((prev) => prev.map((f) => (f.stage_id === stageId ? { ...f, name } : f)))
  }

  const togglePlay = (id: string, url: string) => {
    const fullUrl = audioUrl(url)
    if (playingId === id) {
      audioRefs.current[id]?.pause()
      setPlayingId(null)
      return
    }
    if (playingId && audioRefs.current[playingId]) {
      audioRefs.current[playingId].pause()
    }
    if (!audioRefs.current[id]) {
      audioRefs.current[id] = new Audio(fullUrl)
      audioRefs.current[id].addEventListener('ended', () => setPlayingId(null))
    }
    audioRefs.current[id].play()
    setPlayingId(id)
  }

  const handleImportFolder = async () => {
    setImporting(true)
    setError('')
    try {
      const result = await apiFetch<{
        imported: number
        failed: number
        staged?: { stage_id: string; filename: string; duration: number | null; size: number; audio_url: string }[]
        errors?: { name: string; error: string }[]
        message?: string
      }>('/narrator-voices/import-all', { method: 'POST' })
      setImportResult(result)

      // Add staged files to the list
      if (result.staged && result.staged.length > 0) {
        const newFiles: StagedFile[] = result.staged.map((s) => ({
          stage_id: s.stage_id,
          filename: s.filename,
          ext: 'wav',
          size: s.size,
          duration: s.duration,
          gender: s.gender,
          audio_url: s.audio_url,
          name: autoVoiceName(s.gender),
          status: 'ready' as const,
        }))
        setFiles((prev) => [...prev, ...newFiles])
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import failed')
    } finally {
      setImporting(false)
    }
  }

  // Add all voices (no cloning — just save to DB)
  const handleAddAll = async () => {
    const pending = files.filter((f) => f.status === 'ready')
    if (pending.length === 0) return

    setAdding(true)
    setError('')

    try {
      const payload = pending.map((f) => ({
        stage_id: f.stage_id,
        name: f.name,
        engine,
        language,
      }))

      const result = await apiFetch<{
        added: { stage_id: string; voice_id: string; name: string; quality_score: number }[]
        errors: { stage_id: string; name: string; error: string }[]
        total: number
        failed: number
      }>('/clone/add-voices', {
        method: 'POST',
        body: JSON.stringify(payload),
      })

      // Update file statuses
      setFiles((prev) => prev.map((f) => {
        const added = result.added.find((a) => a.stage_id === f.stage_id)
        if (added) return { ...f, status: 'done' as const, voice_id: added.voice_id, quality_score: added.quality_score }
        const err = result.errors.find((e) => e.stage_id === f.stage_id)
        if (err) return { ...f, status: 'error' as const, error: err.error }
        return f
      }))

      setStep(4)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add voices')
    } finally {
      setAdding(false)
    }
  }

  const formatDuration = (d: number | null) => {
    if (d === null) return '--:--'
    const m = Math.floor(d / 60)
    const s = Math.floor(d % 60)
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const readyCount = files.filter((f) => f.status === 'ready').length
  const doneCount = files.filter((f) => f.status === 'done').length
  const errorCount = files.filter((f) => f.status === 'error').length

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Add Voices</h1>
        <p className="text-sm text-zinc-500 mt-1">Import audio samples, review and name them, then add to your voice library.</p>
      </div>

      {/* Step indicators */}
      <div className="flex items-center gap-3">
        {STEPS.map(({ n, label }) => (
          <div key={n} className="flex items-center gap-2">
            <button
              onClick={() => n < step && setStep(n)}
              disabled={n > step}
              className={`flex items-center justify-center w-8 h-8 rounded-full text-xs font-medium transition-colors ${
                step >= n ? 'bg-violet-500 text-white' : 'bg-zinc-800 text-zinc-500 border border-zinc-700'
              } ${n < step ? 'cursor-pointer hover:bg-violet-600' : ''}`}
            >
              {step > n ? <Check className="w-4 h-4" /> : n}
            </button>
            <span className={`text-xs ${step >= n ? 'text-zinc-300' : 'text-zinc-600'}`}>{label}</span>
            {n < 4 && <div className={`w-8 h-px ${step > n ? 'bg-violet-500' : 'bg-zinc-700'}`} />}
          </div>
        ))}
      </div>

      {error && (
        <div className="px-4 py-3 bg-red-500/5 border border-red-500/20 rounded-xl text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Step 1: Import */}
      {step === 1 && (
        <div className="space-y-4">
          <div
            className="border-2 border-dashed border-zinc-700 rounded-xl p-10 text-center cursor-pointer hover:border-violet-500/50 transition-colors"
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files)
            }}
          >
            <input
              ref={fileRef}
              type="file"
              accept=".wav,.mp3,.ogg,.flac,.m4a,.opus"
              className="hidden"
              multiple
              onChange={(e) => {
                if (e.target.files?.length) addFiles(e.target.files)
                e.target.value = ''
              }}
            />
            {uploading ? (
              <>
                <Loader2 className="w-10 h-10 text-violet-500 mx-auto mb-3 animate-spin" />
                <p className="text-zinc-400">Uploading...</p>
              </>
            ) : (
              <>
                <Upload className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
                <p className="text-zinc-400 mb-1">Drop audio files here or click to browse</p>
                <p className="text-xs text-zinc-600">Multiple files supported — WAV, MP3, OGG, FLAC, M4A, OPUS</p>
              </>
            )}
          </div>

          {/* Batch import */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-medium">Import from Folder</h3>
                <p className="text-xs text-zinc-500 mt-0.5">
                  Place samples in <span className="font-mono text-zinc-400">data/voices/import/</span> then click Import.
                </p>
              </div>
              <button
                onClick={handleImportFolder}
                disabled={importing}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-xl text-xs font-medium hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
              >
                {importing ? <Loader2 className="w-3 h-3 animate-spin" /> : <FolderOpen className="w-3 h-3" />}
                {importing ? 'Importing...' : 'Import All'}
              </button>
            </div>
            {importResult && (
              <div className="mt-3 pt-3 border-t border-zinc-800 flex items-center gap-4">
                <p className="text-xs text-emerald-400">{importResult.imported} voices added directly</p>
                {importResult.failed > 0 && <p className="text-xs text-red-400">{importResult.failed} failed</p>}
              </div>
            )}
          </div>

          {/* Staged file list */}
          {files.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-zinc-300">{files.length} file{files.length !== 1 ? 's' : ''} staged</h3>
                <button
                  onClick={() => setStep(2)}
                  className="flex items-center gap-1.5 px-5 py-2 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 rounded-xl text-sm font-medium transition-all"
                >
                  Review Files <ChevronRight className="w-4 h-4" />
                </button>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl divide-y divide-zinc-800">
                {files.map((uf) => (
                  <div key={uf.stage_id} className="flex items-center gap-3 px-4 py-2.5">
                    <Mic className="w-3.5 h-3.5 text-zinc-600 shrink-0" />
                    <span className="text-sm text-zinc-300 truncate flex-1">{uf.filename}</span>
                    <span className="text-xs text-zinc-500">{formatDuration(uf.duration)}</span>
                    <span className="text-xs text-zinc-600">{(uf.size / 1024).toFixed(0)} KB</span>
                    <button onClick={() => removeFile(uf.stage_id)} className="text-zinc-600 hover:text-red-400">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Review — play, rename, remove */}
      {step === 2 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-zinc-300">Review & Name Your Voices</h3>
            <span className="text-xs text-zinc-500">{files.length} file{files.length !== 1 ? 's' : ''}</span>
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-xl divide-y divide-zinc-800">
            {files.map((uf) => (
              <div key={uf.stage_id} className="flex items-center gap-3 px-4 py-3">
                <button
                  onClick={() => togglePlay(uf.stage_id, uf.audio_url)}
                  className="w-8 h-8 shrink-0 flex items-center justify-center rounded-lg bg-zinc-800 hover:bg-zinc-700 transition-colors"
                >
                  {playingId === uf.stage_id
                    ? <Pause className="w-3.5 h-3.5 text-violet-400" />
                    : <Play className="w-3.5 h-3.5 text-zinc-400 ml-0.5" />}
                </button>
                <input
                  value={uf.name}
                  onChange={(e) => updateFileName(uf.stage_id, e.target.value)}
                  className="flex-1 px-3 py-1.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm focus:outline-none focus:border-violet-500"
                  placeholder="Voice name..."
                />
                {uf.gender && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                    uf.gender === 'Female' ? 'bg-pink-500/10 text-pink-400' : 'bg-blue-500/10 text-blue-400'
                  }`}>{uf.gender}</span>
                )}
                <span className="text-xs text-zinc-500 w-12 text-right">{formatDuration(uf.duration)}</span>
                <span className="text-xs text-zinc-600 w-16 text-right">{(uf.size / 1024).toFixed(0)} KB</span>
                <button onClick={() => removeFile(uf.stage_id)} className="text-zinc-600 hover:text-red-400">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>

          {files.length === 0 && (
            <div className="text-center py-8 text-zinc-500 text-sm">No files staged. Go back to import some.</div>
          )}

          <div className="flex gap-3">
            <button
              onClick={() => setStep(3)}
              disabled={files.length === 0}
              className="flex items-center gap-1.5 px-6 py-2.5 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 disabled:from-zinc-700 disabled:to-zinc-700 disabled:opacity-50 rounded-xl text-sm font-medium transition-all"
            >
              Configure <Settings2 className="w-4 h-4" />
            </button>
            <button onClick={() => setStep(1)} className="px-4 py-2.5 bg-zinc-800 hover:bg-zinc-700 rounded-xl text-sm text-zinc-400">Back</button>
          </div>
        </div>
      )}

      {/* Step 3: Configure & Add */}
      {step === 3 && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-zinc-400 mb-2">Engine</label>
              <select value={engine} onChange={(e) => setEngine(e.target.value)}
                className="w-full px-4 py-3 bg-zinc-900 border border-zinc-800 rounded-xl text-sm">
                {ENGINES.map((e) => <option key={e.value} value={e.value}>{e.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm text-zinc-400 mb-2">Language</label>
              <select value={language} onChange={(e) => setLanguage(e.target.value)}
                className="w-full px-4 py-3 bg-zinc-900 border border-zinc-800 rounded-xl text-sm">
                {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
              </select>
            </div>
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
            <h3 className="text-xs text-zinc-500 uppercase tracking-wide mb-3">
              Will add {readyCount} voice{readyCount !== 1 ? 's' : ''} to library
            </h3>
            <div className="space-y-1.5">
              {files.filter((f) => f.status === 'ready').map((uf) => (
                <div key={uf.stage_id} className="flex items-center gap-2 text-sm">
                  <Mic className="w-3 h-3 text-violet-400" />
                  <span className="text-zinc-300">{uf.name}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={handleAddAll}
              disabled={adding || readyCount === 0}
              className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 disabled:from-zinc-700 disabled:to-zinc-700 disabled:opacity-50 rounded-xl text-sm font-medium transition-all"
            >
              {adding ? <><Loader2 className="w-4 h-4 animate-spin" /> Adding...</> : `Add ${readyCount} Voice${readyCount !== 1 ? 's' : ''}`}
            </button>
            <button onClick={() => setStep(2)} disabled={adding} className="px-4 py-2.5 bg-zinc-800 hover:bg-zinc-700 rounded-xl text-sm text-zinc-400 disabled:opacity-50">Back</button>
          </div>
        </div>
      )}

      {/* Step 4: Done */}
      {step === 4 && (
        <div className="space-y-6">
          <div className="text-center py-8">
            <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center mx-auto mb-4">
              <Check className="w-8 h-8 text-emerald-400" />
            </div>
            <h2 className="text-lg font-medium mb-2">
              {doneCount} Voice{doneCount !== 1 ? 's' : ''} Added!
            </h2>
            {errorCount > 0 && <p className="text-sm text-red-400">{errorCount} failed</p>}
            <p className="text-sm text-zinc-400 mt-1">Ready to use in Studio and Audiobooks.</p>
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-xl divide-y divide-zinc-800">
            {files.map((uf) => (
              <div key={uf.stage_id} className="flex items-center gap-3 px-4 py-3">
                {uf.status === 'done'
                  ? <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                  : <span className="w-4 h-4 text-red-400 text-xs shrink-0">!</span>}
                <span className="text-sm text-zinc-300 flex-1">{uf.name}</span>
                {uf.status === 'done' && <span className="text-xs text-zinc-500">Quality: {uf.quality_score}/5</span>}
                {uf.status === 'error' && <span className="text-xs text-red-400">{uf.error}</span>}
              </div>
            ))}
          </div>

          <button
            onClick={() => { setStep(1); setFiles([]); setImportResult(null); setError('') }}
            className="px-6 py-2.5 bg-zinc-800 hover:bg-zinc-700 rounded-xl text-sm"
          >
            Add More Voices
          </button>
        </div>
      )}
    </div>
  )
}
