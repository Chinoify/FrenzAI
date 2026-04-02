import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Play, Pause, ChevronDown, ChevronRight, Loader2, CheckCircle2,
  AlertCircle, Download, Sparkles, ArrowLeft, Volume2, Plus, Trash2,
  Edit3, GripVertical, FileAudio, Settings2, BookOpen, X, Save
} from 'lucide-react'
import { useProjectStore } from '../stores/projectStore'
import { useVoiceStore } from '../stores/voiceStore'
import { useAppStore } from '../stores/appStore'
import { apiFetch, audioUrl } from '../lib/api'
import type { Chapter } from '../types'

type ExportFormat = 'wav' | 'mp3' | 'mp3-acx' | 'lpf'

export default function ProjectEditor() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const {
    currentProject, fetchProject, updateChapter, createChapter, deleteChapter,
    generateChapter, generateAll, mergeExport, exportChaptersACX,
    generating, generationProgress, kokoroVoices, fetchKokoroVoices
  } = useProjectStore()
  const { voices, fetchVoices } = useVoiceStore()
  const { models, fetchModels } = useAppStore()

  const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState<string | null>(null)
  const [editTitleValue, setEditTitleValue] = useState('')
  const [editingText, setEditingText] = useState(false)
  const [editTextValue, setEditTextValue] = useState('')
  const [playingChapter, setPlayingChapter] = useState<string | null>(null)
  const [exportFormat, setExportFormat] = useState<ExportFormat>('mp3-acx')
  const [exporting, setExporting] = useState(false)
  const [showNewChapter, setShowNewChapter] = useState(false)
  const [newChapterTitle, setNewChapterTitle] = useState('')
  const [newChapterText, setNewChapterText] = useState('')
  const [showExportPanel, setShowExportPanel] = useState(false)
  const [testingVoice, setTestingVoice] = useState(false)
  const [exportProgress, setExportProgress] = useState<{ pct: number; message: string } | null>(null)
  const [selectedEngine, setSelectedEngine] = useState('')
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    if (id) {
      fetchProject(id)
      fetchVoices()
      fetchKokoroVoices()
      fetchModels()
    }
  }, [id, fetchProject, fetchVoices, fetchKokoroVoices])

  // Auto-select first chapter + sync engine
  useEffect(() => {
    if (currentProject?.chapters.length && !selectedChapterId) {
      setSelectedChapterId(currentProject.chapters[0].id)
    }
    if (currentProject && !selectedEngine) {
      setSelectedEngine(currentProject.default_model || 'kokoro')
    }
  }, [currentProject, selectedChapterId, selectedEngine])

  if (!currentProject) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-violet-500" />
      </div>
    )
  }

  const selectedChapter = currentProject.chapters.find((ch) => ch.id === selectedChapterId)
  const completedCount = currentProject.chapters.filter((ch) => ch.status === 'completed').length
  const totalDuration = currentProject.chapters.reduce((sum, ch) => sum + (ch.duration || 0), 0)

  const statusIcon = (status: string, size = 'w-3 h-3') => {
    switch (status) {
      case 'completed': return <CheckCircle2 className={`${size} text-green-400`} />
      case 'generating': return <Loader2 className={`${size} text-yellow-400 animate-spin`} />
      case 'edited': return <Edit3 className={`${size} text-orange-400`} />
      case 'error': return <AlertCircle className={`${size} text-red-400`} />
      default: return <div className={`${size} rounded-full border-2 border-zinc-600`} />
    }
  }

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = Math.round(seconds % 60)
    return m > 0 ? `${m}m ${s}s` : `${s}s`
  }

  const handlePlayChapter = (chapter: Chapter) => {
    if (!chapter.audio_url) return
    if (playingChapter === chapter.id) {
      audioRef.current?.pause()
      setPlayingChapter(null)
      return
    }
    if (audioRef.current) audioRef.current.pause()
    const audio = new Audio(audioUrl(chapter.audio_url))
    audio.onended = () => setPlayingChapter(null)
    audio.play()
    audioRef.current = audio
    setPlayingChapter(chapter.id)
  }

  const handleSaveText = async () => {
    if (selectedChapterId && editingText) {
      await updateChapter(currentProject.id, selectedChapterId, { text: editTextValue })
      setEditingText(false)
    }
  }

  const handleTestVoice = async () => {
    if (!selectedChapter) return
    setTestingVoice(true)
    try {
      const voiceModel = selectedChapter.model || currentProject.default_model || 'kokoro'
      let voiceCode = 'af_heart' // default

      // Extract kokoro voice code
      if (voiceModel.startsWith('kokoro:')) {
        voiceCode = voiceModel.split(':')[1]
      }

      // Use fast cached preview endpoint
      const result = await apiFetch<{ audio_url: string }>(`/tts/preview/${voiceCode}`)
      if (audioRef.current) audioRef.current.pause()
      const audio = new Audio(audioUrl(result.audio_url))
      audio.onended = () => setTestingVoice(false)
      audio.play()
      audioRef.current = audio
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Voice test failed')
    } finally {
      setTestingVoice(false)
    }
  }

  const handleRenameChapter = async (chapterId: string) => {
    if (editTitleValue.trim()) {
      await updateChapter(currentProject.id, chapterId, { title: editTitleValue })
    }
    setEditingTitle(null)
  }

  const handleAddChapter = async () => {
    if (!newChapterTitle.trim()) return
    await createChapter(
      currentProject.id,
      newChapterTitle,
      newChapterText || 'Enter chapter text here...',
    )
    setShowNewChapter(false)
    setNewChapterTitle('')
    setNewChapterText('')
  }

  const handleDeleteChapter = async (chapterId: string) => {
    if (!confirm('Delete this chapter? This cannot be undone.')) return
    await deleteChapter(currentProject.id, chapterId)
    if (selectedChapterId === chapterId) {
      setSelectedChapterId(currentProject.chapters[0]?.id || null)
    }
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const isACX = exportFormat === 'mp3-acx'
      const fmt = isACX ? 'mp3' : exportFormat
      await mergeExport(currentProject.id, fmt, isACX)
      const a = document.createElement('a')
      a.href = `/api/projects/${currentProject.id}/export`
      a.download = `${currentProject.name.replace(/[^a-zA-Z0-9 _-]/g, '').replace(/\s+/g, '_')}.${exportFormat === 'mp3-acx' ? 'mp3' : exportFormat}`
      a.click()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  const handleExportChaptersACX = async () => {
    setExporting(true)
    try {
      const result = await exportChaptersACX(currentProject.id) as any
      if (result?.chapters) {
        for (const ch of result.chapters) {
          if (ch.url) {
            const a = document.createElement('a')
            a.href = audioUrl(ch.url)
            a.download = `${currentProject.name.replace(/[^a-zA-Z0-9 _-]/g, '').replace(/\s+/g, '_')}_${ch.title.replace(/[^a-zA-Z0-9 _-]/g, '').replace(/\s+/g, '_')}.mp3`
            a.click()
          }
        }
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Export failed')
    } finally {
      setExporting(false)
    }
  }


  const handleExportZip = async () => {
    setExporting(true)
    setExportProgress({ pct: 0, message: 'Starting export...' })
    try {
      const res = await fetch(`/api/projects/${currentProject.id}/export-zip-progress`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format: exportFormat }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Export failed' }))
        throw new Error(err.detail)
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let downloadUrl = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.pct !== undefined) {
                setExportProgress({ pct: data.pct, message: data.message || '' })
              }
              if (data.download_url) {
                downloadUrl = data.download_url
              }
            } catch {}
          }
        }
      }

      // Download the zip
      if (downloadUrl) {
        setExportProgress({ pct: 100, message: 'Downloading...' })
        const a = document.createElement('a')
        a.href = downloadUrl
        a.download = `${currentProject.name.replace(/[^a-zA-Z0-9 _-]/g, '').replace(/\s+/g, '_')}_chapters.zip`
        a.click()
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Export failed')
    } finally {
      setExporting(false)
      setTimeout(() => setExportProgress(null), 2000)
    }
  }

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden">
      {/* LEFT SIDEBAR — Chapter List */}
      <div className="w-72 flex-shrink-0 bg-zinc-950 border-r border-zinc-800 flex flex-col">
        {/* Project header */}
        <div className="p-3 border-b border-zinc-800">
          <div className="flex items-center gap-2 mb-2">
            <button onClick={() => navigate('/projects')} className="text-zinc-400 hover:text-zinc-200">
              <ArrowLeft className="w-4 h-4" />
            </button>
            <h2 className="text-sm font-semibold truncate flex-1">{currentProject.name}</h2>
          </div>
          <div className="flex items-center gap-3 text-xs text-zinc-500">
            <span>{currentProject.chapters.length} chapters</span>
            <span>{completedCount} generated</span>
            {totalDuration > 0 && <span>{formatDuration(totalDuration)}</span>}
          </div>
        </div>

        {/* Engine selector + Generate all */}
        <div className="p-2 border-b border-zinc-800 space-y-2">
          <select
            value={selectedEngine}
            onChange={(e) => setSelectedEngine(e.target.value)}
            className="w-full px-2 py-1.5 bg-zinc-800 border border-zinc-700 rounded text-xs"
          >
            {models.length > 0 ? (
              models.map((m) => (
                <option key={m.name} value={m.name}>{m.display_name}</option>
              ))
            ) : (
              <>
                <option value="kokoro">Kokoro</option>
                <option value="chatterbox">Chatterbox</option>
                <option value="builtin">Built-in</option>
              </>
            )}
          </select>
          <button
            onClick={() => generateAll(currentProject.id, undefined, selectedEngine)}
            disabled={generating}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-violet-500 hover:bg-violet-600 disabled:bg-zinc-700 rounded-lg text-xs font-medium transition-colors"
          >
            {generating ? (
              <><Loader2 className="w-3 h-3 animate-spin" /> Generating...</>
            ) : (
              <><Sparkles className="w-3 h-3" /> Generate All Chapters</>
            )}
          </button>
          {generating && generationProgress && (
            <p className="text-[10px] text-zinc-500 text-center mt-1">
              {generationProgress.chapter}/{generationProgress.total}: {generationProgress.title}
            </p>
          )}
        </div>

        {/* Chapter list */}
        <div className="flex-1 overflow-y-auto">
          {currentProject.chapters.map((chapter) => (
            <div
              key={chapter.id}
              onClick={() => {
                setSelectedChapterId(chapter.id)
                setEditingText(false)
              }}
              className={`group flex items-center gap-2 px-3 py-2.5 cursor-pointer border-l-2 transition-colors ${
                selectedChapterId === chapter.id
                  ? 'bg-zinc-800/80 border-violet-500 text-white'
                  : 'border-transparent hover:bg-zinc-900 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {statusIcon(chapter.status)}

              {editingTitle === chapter.id ? (
                <input
                  value={editTitleValue}
                  onChange={(e) => setEditTitleValue(e.target.value)}
                  onBlur={() => handleRenameChapter(chapter.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleRenameChapter(chapter.id)
                    if (e.key === 'Escape') setEditingTitle(null)
                  }}
                  className="flex-1 bg-zinc-700 px-1 py-0.5 rounded text-xs focus:outline-none"
                  autoFocus
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <span className="flex-1 text-xs truncate">{chapter.title}</span>
              )}

              {chapter.duration && (
                <span className="text-[10px] text-zinc-600">{Math.round(chapter.duration)}s</span>
              )}

              {/* Chapter actions */}
              <div className="hidden group-hover:flex items-center gap-0.5">
                {chapter.audio_url && (
                  <button
                    onClick={(e) => { e.stopPropagation(); handlePlayChapter(chapter) }}
                    className="p-0.5 hover:text-violet-400"
                  >
                    {playingChapter === chapter.id ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                  </button>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setEditingTitle(chapter.id)
                    setEditTitleValue(chapter.title)
                  }}
                  className="p-0.5 hover:text-blue-400"
                >
                  <Edit3 className="w-3 h-3" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDeleteChapter(chapter.id) }}
                  className="p-0.5 hover:text-red-400"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Add chapter */}
        <div className="p-2 border-t border-zinc-800">
          {showNewChapter ? (
            <div className="space-y-2">
              <input
                value={newChapterTitle}
                onChange={(e) => setNewChapterTitle(e.target.value)}
                placeholder="Chapter title"
                className="w-full px-2 py-1.5 bg-zinc-800 border border-zinc-700 rounded text-xs focus:outline-none focus:border-violet-500"
                autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter') handleAddChapter() }}
              />
              <div className="flex gap-1">
                <button
                  onClick={handleAddChapter}
                  disabled={!newChapterTitle.trim()}
                  className="flex-1 px-2 py-1 bg-violet-500 hover:bg-violet-600 disabled:bg-zinc-700 rounded text-xs"
                >
                  Add
                </button>
                <button
                  onClick={() => setShowNewChapter(false)}
                  className="px-2 py-1 bg-zinc-700 hover:bg-zinc-600 rounded text-xs"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowNewChapter(true)}
              className="w-full flex items-center justify-center gap-1 px-2 py-1.5 bg-zinc-800 hover:bg-zinc-700 rounded text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              <Plus className="w-3 h-3" /> Add Chapter
            </button>
          )}
        </div>
      </div>

      {/* MAIN CONTENT — Chapter Editor */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {selectedChapter ? (
          <>
            {/* Chapter toolbar */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-zinc-800 bg-zinc-900/50">
              <div className="flex items-center gap-2 flex-1">
                {statusIcon(selectedChapter.status, 'w-4 h-4')}
                <h3 className="text-sm font-medium">{selectedChapter.title}</h3>
                {selectedChapter.duration && (
                  <span className="text-xs text-zinc-500">{formatDuration(selectedChapter.duration)}</span>
                )}
                <span className="text-xs text-zinc-600">
                  {selectedChapter.text.length.toLocaleString()} chars
                </span>
              </div>

              {/* Voice picker per chapter */}
              <select
                value={selectedChapter.voice_id || (selectedChapter.model?.startsWith('kokoro:') ? selectedChapter.model.split(':')[1] : selectedChapter.model) || ''}
                onChange={async (e) => {
                  const val = e.target.value
                  const isKokoroVoice = kokoroVoices.some((v) => v.code === val)
                  const clonedVoice = voices.find((v) => v.id === val)
                  if (isKokoroVoice) {
                    await apiFetch(`/projects/${currentProject.id}/chapters/${selectedChapter.id}`, {
                      method: 'PATCH',
                      body: JSON.stringify({ voice_id: '', model: `kokoro:${val}` }),
                    })
                  } else if (clonedVoice) {
                    // Cloned voice — store voice_id and its engine
                    await apiFetch(`/projects/${currentProject.id}/chapters/${selectedChapter.id}`, {
                      method: 'PATCH',
                      body: JSON.stringify({ voice_id: val, model: clonedVoice.engine || 'chatterbox' }),
                    })
                  } else {
                    await apiFetch(`/projects/${currentProject.id}/chapters/${selectedChapter.id}`, {
                      method: 'PATCH',
                      body: JSON.stringify({ voice_id: '', model: '' }),
                    })
                  }
                  await fetchProject(currentProject.id)
                }}
                className="px-2 py-1.5 bg-zinc-800 border border-zinc-700 rounded text-xs max-w-[200px]"
              >
                <option value="">Default Voice (Heart)</option>
                {voices.length > 0 && (
                  <optgroup label="🎤 My Cloned Voices">
                    {voices.map((v) => (
                      <option key={v.id} value={v.id}>{v.name}</option>
                    ))}
                  </optgroup>
                )}
                <optgroup label="🇺🇸 English (US) Female">
                  {kokoroVoices.filter((v) => v.language === 'en' && v.gender === 'female').map((v) => (
                    <option key={v.code} value={v.code}>{v.name}</option>
                  ))}
                </optgroup>
                <optgroup label="🇺🇸 English (US) Male">
                  {kokoroVoices.filter((v) => v.language === 'en' && v.gender === 'male').map((v) => (
                    <option key={v.code} value={v.code}>{v.name}</option>
                  ))}
                </optgroup>
                <optgroup label="🇬🇧 English (UK) Female">
                  {kokoroVoices.filter((v) => v.language === 'en-gb' && v.gender === 'female').map((v) => (
                    <option key={v.code} value={v.code}>{v.name}</option>
                  ))}
                </optgroup>
                <optgroup label="🇬🇧 English (UK) Male">
                  {kokoroVoices.filter((v) => v.language === 'en-gb' && v.gender === 'male').map((v) => (
                    <option key={v.code} value={v.code}>{v.name}</option>
                  ))}
                </optgroup>
                {kokoroVoices.some((v) => !['en', 'en-gb', 'zh'].includes(v.language)) && (
                  <optgroup label="🌍 Other Languages">
                    {kokoroVoices.filter((v) => !['en', 'en-gb', 'zh'].includes(v.language)).map((v) => (
                      <option key={v.code} value={v.code}>{v.name}</option>
                    ))}
                  </optgroup>
                )}
              </select>

              {selectedChapter.audio_url && (
                <button
                  onClick={() => handlePlayChapter(selectedChapter)}
                  className={`flex items-center gap-1 px-3 py-1.5 rounded text-xs transition-colors ${
                    playingChapter === selectedChapter.id
                      ? 'bg-violet-500/20 text-violet-400'
                      : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300'
                  }`}
                >
                  {playingChapter === selectedChapter.id ? (
                    <><Pause className="w-3 h-3" /> Playing</>
                  ) : (
                    <><Volume2 className="w-3 h-3" /> Preview</>
                  )}
                </button>
              )}

              <button
                onClick={handleTestVoice}
                disabled={testingVoice || generating}
                className="flex items-center gap-1 px-3 py-1.5 bg-zinc-700 hover:bg-zinc-600 disabled:bg-zinc-700 rounded text-xs transition-colors"
              >
                {testingVoice ? <Loader2 className="w-3 h-3 animate-spin" /> : <Volume2 className="w-3 h-3" />}
                Test Voice
              </button>

              <button
                onClick={() => generateChapter(currentProject.id, selectedChapter.id)}
                disabled={generating}
                className="flex items-center gap-1 px-3 py-1.5 bg-violet-500 hover:bg-violet-600 disabled:bg-zinc-700 rounded text-xs font-medium transition-colors"
              >
                {generating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                Generate
              </button>
            </div>

            {/* Text editor area */}
            <div className="flex-1 overflow-y-auto p-4">
              {editingText ? (
                <div className="h-full flex flex-col">
                  <textarea
                    value={editTextValue}
                    onChange={(e) => setEditTextValue(e.target.value)}
                    className="flex-1 w-full px-4 py-3 bg-zinc-900 border border-zinc-700 rounded-lg text-sm leading-relaxed resize-none focus:outline-none focus:border-violet-500 font-mono"
                    placeholder="Enter chapter text..."
                  />
                  <div className="flex items-center gap-2 mt-3">
                    <button
                      onClick={handleSaveText}
                      className="flex items-center gap-1 px-4 py-2 bg-violet-500 hover:bg-violet-600 rounded-lg text-xs font-medium"
                    >
                      <Save className="w-3 h-3" /> Save Changes
                    </button>
                    <button
                      onClick={() => setEditingText(false)}
                      className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg text-xs"
                    >
                      Cancel
                    </button>
                    <span className="text-xs text-zinc-500 ml-auto">
                      {editTextValue.length.toLocaleString()} characters
                    </span>
                  </div>
                </div>
              ) : (
                <div
                  className="prose prose-invert prose-sm max-w-none cursor-pointer hover:bg-zinc-900/50 rounded-lg p-4 transition-colors min-h-[200px]"
                  onClick={() => {
                    setEditingText(true)
                    setEditTextValue(selectedChapter.text)
                  }}
                >
                  <p className="text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">
                    {selectedChapter.text}
                  </p>
                  <p className="text-xs text-zinc-600 mt-4 italic">Click anywhere to edit</p>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-zinc-600">
            <div className="text-center">
              <BookOpen className="w-10 h-10 mx-auto mb-2" />
              <p className="text-sm">Select a chapter to edit</p>
            </div>
          </div>
        )}
      </div>

      {/* RIGHT SIDEBAR — Export Options */}
      <div className="w-64 flex-shrink-0 bg-zinc-950 border-l border-zinc-800 flex flex-col">
        <div className="p-3 border-b border-zinc-800">
          <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Export</h3>
        </div>

        <div className="p-3 space-y-4 flex-1 overflow-y-auto">
          {/* Format selection */}
          <div>
            <label className="text-xs text-zinc-500 block mb-2">Format</label>
            <div className="space-y-1">
              {[
                { value: 'mp3-acx' as ExportFormat, label: 'MP3 — ACX Standard', desc: '192kbps CBR, 44.1kHz, Mono' },
                { value: 'mp3' as ExportFormat, label: 'MP3', desc: '192kbps, Standard' },
                { value: 'wav' as ExportFormat, label: 'WAV', desc: 'Lossless, Large files' },
                { value: 'lpf' as ExportFormat, label: 'LPF', desc: 'ElevenLabs format' },
              ].map((fmt) => (
                <label
                  key={fmt.value}
                  className={`flex items-start gap-2 p-2 rounded cursor-pointer transition-colors ${
                    exportFormat === fmt.value
                      ? 'bg-violet-500/10 border border-violet-500/30'
                      : 'hover:bg-zinc-800 border border-transparent'
                  }`}
                >
                  <input
                    type="radio"
                    name="format"
                    value={fmt.value}
                    checked={exportFormat === fmt.value}
                    onChange={() => setExportFormat(fmt.value)}
                    className="mt-0.5 accent-violet-500"
                  />
                  <div>
                    <p className="text-xs font-medium">{fmt.label}</p>
                    <p className="text-[10px] text-zinc-500">{fmt.desc}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* ACX Info */}
          {exportFormat === 'mp3-acx' && (
            <div className="bg-green-500/5 border border-green-500/20 rounded-lg p-2.5">
              <p className="text-[10px] text-green-400 font-medium mb-1">ACX Compliance</p>
              <ul className="text-[10px] text-zinc-500 space-y-0.5">
                <li>- 192 kbps CBR, 44.1 kHz</li>
                <li>- Peaks at -3dB max</li>
                <li>- RMS: -23dB to -18dB</li>
                <li>- Noise floor below -60dB</li>
                <li>- 0.75s silence at start</li>
                <li>- 2.5s silence at end</li>
                <li>- Mono channel</li>
              </ul>
            </div>
          )}

          {/* Export buttons */}
          <div className="space-y-2">
            <button
              onClick={handleExport}
              disabled={completedCount === 0 || exporting}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-violet-500 hover:bg-violet-600 disabled:bg-zinc-700 disabled:opacity-50 rounded-lg text-xs font-medium transition-colors"
            >
              <Download className="w-3 h-3" />
              {exporting ? 'Exporting...' : 'Export Full Audiobook'}
            </button>

            {exportFormat === 'mp3-acx' && (
              <button
                onClick={handleExportChaptersACX}
                disabled={completedCount === 0 || exporting}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50 rounded-lg text-xs transition-colors"
              >
                <FileAudio className="w-3 h-3" />
                Export Each Chapter (ACX)
              </button>
            )}

            <button
              onClick={handleExportZip}
              disabled={completedCount === 0 || exporting}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 disabled:opacity-50 rounded-lg text-xs transition-colors border border-blue-500/20"
            >
              <Download className="w-3 h-3" />
              {exporting ? 'Exporting...' : `Export All as ZIP (${exportFormat.toUpperCase()})`}
            </button>

            {/* Export progress bar */}
            {exportProgress && (
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-zinc-400">
                  <span>{exportProgress.message}</span>
                  <span>{exportProgress.pct}%</span>
                </div>
                <div className="w-full bg-zinc-800 rounded-full h-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${exportProgress.pct}%` }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Stats */}
          <div className="border-t border-zinc-800 pt-3">
            <h4 className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">Stats</h4>
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-zinc-500">Chapters</span>
                <span>{currentProject.chapters.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Generated</span>
                <span className="text-green-400">{completedCount}/{currentProject.chapters.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Duration</span>
                <span>{totalDuration > 0 ? formatDuration(totalDuration) : '—'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Characters</span>
                <span>{currentProject.chapters.reduce((s, ch) => s + ch.text.length, 0).toLocaleString()}</span>
              </div>
            </div>
          </div>

          {/* Progress bar */}
          {currentProject.chapters.length > 0 && (
            <div>
              <div className="flex justify-between text-[10px] text-zinc-500 mb-1">
                <span>Progress</span>
                <span>{Math.round((completedCount / currentProject.chapters.length) * 100)}%</span>
              </div>
              <div className="w-full bg-zinc-800 rounded-full h-1.5">
                <div
                  className="bg-violet-500 h-1.5 rounded-full transition-all"
                  style={{ width: `${(completedCount / currentProject.chapters.length) * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
