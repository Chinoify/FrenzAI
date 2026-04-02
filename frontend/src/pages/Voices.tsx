import { useEffect, useState, useRef } from 'react'
import { Star, Trash2, Play, Pause, Search, Volume2, Loader2, Mic, Download, Plus, X } from 'lucide-react'
import { useVoiceStore } from '../stores/voiceStore'
import { useProjectStore } from '../stores/projectStore'
import { apiFetch, audioUrl, BACKEND_URL } from '../lib/api'
import LoadingSpinner from '../components/common/LoadingSpinner'

export default function Voices() {
  const { voices, loading, fetchVoices, toggleFavorite, deleteVoice } = useVoiceStore()
  const { kokoroVoices, fetchKokoroVoices } = useProjectStore()
  const [playingId, setPlayingId] = useState<string | null>(null)
  const [previewingId, setPreviewingId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [langFilter, setLangFilter] = useState('all')
  const audioRef = useRef<HTMLAudioElement | null>(null)

  // Voice blending state
  const [showBlend, setShowBlend] = useState(false)
  const [blendSlots, setBlendSlots] = useState([
    { code: 'af_heart', weight: 70 },
    { code: 'am_adam', weight: 30 },
  ])
  const [blendName, setBlendName] = useState('')
  const [blending, setBlending] = useState(false)

  // Narrator download state
  const [downloadingNarrators, setDownloadingNarrators] = useState(false)
  const [narratorProgress, setNarratorProgress] = useState<{ current: number; total: number; name: string } | null>(null)

  useEffect(() => {
    fetchVoices()
    fetchKokoroVoices()
  }, [fetchVoices, fetchKokoroVoices])

  const handlePlayPause = (id: string, url: string) => {
    if (playingId === id) {
      audioRef.current?.pause()
      setPlayingId(null)
      return
    }
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    const audio = new Audio(url)
    audio.onended = () => { setPlayingId(null); audioRef.current = null }
    audio.onerror = () => { setPlayingId(null); audioRef.current = null }
    audio.play()
    audioRef.current = audio
    setPlayingId(id)
  }

  const handlePreviewNarrator = async (voiceId: string, voiceName: string) => {
    if (playingId === voiceId) {
      audioRef.current?.pause()
      setPlayingId(null)
      return
    }
    setPreviewingId(voiceId)
    try {
      // Generate a quick preview using the narrator's blended voice
      const result = await apiFetch<{ audio_url: string; duration: number }>('/tts/generate', {
        method: 'POST',
        body: JSON.stringify({
          text: `Hello, my name is ${voiceName}. I will be narrating your audiobook today.`,
          model: 'kokoro',
          voice_id: voiceId,
          language: 'en',
          speed: 1.0,
        }),
      })
      handlePlayPause(voiceId, audioUrl(result.audio_url))
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Preview failed')
    } finally {
      setPreviewingId(null)
    }
  }

  const handlePreviewKokoro = async (voiceCode: string) => {
    // If already playing this voice, just pause
    if (playingId === voiceCode) {
      audioRef.current?.pause()
      setPlayingId(null)
      return
    }
    setPreviewingId(voiceCode)
    try {
      // Use fast cached preview endpoint
      const result = await apiFetch<{ audio_url: string }>(`/tts/preview/${voiceCode}`)
      handlePlayPause(voiceCode, audioUrl(result.audio_url))
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Preview failed')
    } finally {
      setPreviewingId(null)
    }
  }

  const handleBlend = async () => {
    if (!blendName.trim()) return
    setBlending(true)
    try {
      const normalizedSlots = blendSlots.map((s) => ({ code: s.code, weight: s.weight / 100 }))
      await apiFetch('/voices/blend', {
        method: 'POST',
        body: JSON.stringify({ voices: normalizedSlots, name: blendName, language: 'en' }),
      })
      await fetchVoices()
      setShowBlend(false)
      setBlendName('')
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Blend failed')
    } finally {
      setBlending(false)
    }
  }

  const handleDownloadNarrators = async () => {
    setDownloadingNarrators(true)
    setNarratorProgress(null)
    try {
      const res = await fetch(`${BACKEND_URL || ''}/api/narrator-voices/seed`, { method: 'POST' })
      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
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
              if (data.progress) setNarratorProgress({ current: data.progress, total: data.total, name: data.name })
              if (data.status === 'done') break
            } catch {}
          }
        }
      }
      await fetchVoices()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Download failed')
    } finally {
      setDownloadingNarrators(false)
      setNarratorProgress(null)
    }
  }

  // Separate narrator voices from user-cloned voices
  const narratorVoices = voices.filter((v) => v.tags?.includes('narrator'))
  const userVoices = voices.filter((v) => !v.tags?.includes('narrator'))

  const filteredUserVoices = userVoices.filter((v) =>
    (!search || v.name.toLowerCase().includes(search.toLowerCase())) &&
    (langFilter === 'all' || v.language === langFilter)
  )

  const filteredNarrators = narratorVoices.filter((v) =>
    (!search || v.name.toLowerCase().includes(search.toLowerCase())) &&
    (langFilter === 'all' || v.language === langFilter)
  )

  const filteredKokoro = kokoroVoices.filter((v) =>
    (!search || v.name.toLowerCase().includes(search.toLowerCase())) &&
    (langFilter === 'all' || v.language === langFilter)
  )

  const langLabels: Record<string, string> = {
    'en': '🇺🇸 English (US)', 'en-gb': '🇬🇧 English (UK)', 'ja': '🇯🇵 Japanese',
    'zh': '🇨🇳 Chinese', 'es': '🇪🇸 Spanish', 'fr': '🇫🇷 French',
    'hi': '🇮🇳 Hindi', 'it': '🇮🇹 Italian', 'pt': '🇧🇷 Portuguese',
    'de': '🇩🇪 German',
  }

  // Group narrators by language
  const narratorsByLang = filteredNarrators.reduce<Record<string, typeof filteredNarrators>>((acc, v) => {
    const lang = v.language || 'en'
    if (!acc[lang]) acc[lang] = []
    acc[lang].push(v)
    return acc
  }, {})

  if (loading) {
    return <div className="flex items-center justify-center h-64"><LoadingSpinner /></div>
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Voice Library</h1>
        <span className="text-xs text-zinc-500">{userVoices.length} cloned + {narratorVoices.length} narrators + {kokoroVoices.length} built-in</span>
      </div>

      {/* Search & Filter */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex items-center gap-2 flex-1 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg">
          <Search className="w-4 h-4 text-zinc-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search voices..."
            className="bg-transparent text-sm flex-1 focus:outline-none"
          />
        </div>
        <select
          value={langFilter}
          onChange={(e) => setLangFilter(e.target.value)}
          className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm"
        >
          <option value="all">All Languages</option>
          {Object.entries(langLabels).filter(([code]) => code !== 'zh').map(([code, label]) => (
            <option key={code} value={code}>{label}</option>
          ))}
        </select>
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => setShowBlend(!showBlend)}
          className="flex items-center gap-2 px-4 py-2 bg-violet-500/10 text-violet-400 border border-violet-500/20 rounded-xl text-xs font-medium hover:bg-violet-500/20 transition-colors"
        >
          <Plus className="w-3 h-3" /> Blend Voices
        </button>
      </div>

      {/* Voice Blending Panel */}
      {showBlend && (
        <div className="mb-6 bg-zinc-900 border border-violet-500/20 rounded-xl p-5 space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-violet-400">Create Blended Voice</h3>
              <p className="text-xs text-zinc-500 mt-1">Mix 2-4 Kokoro voices with adjustable weights to create a unique narrator.</p>
            </div>
            <button onClick={() => setShowBlend(false)} className="text-zinc-500 hover:text-zinc-300"><X className="w-4 h-4" /></button>
          </div>

          {/* Voice slots */}
          <div className="space-y-3">
            {blendSlots.map((slot, i) => {
              const selectedVoice = kokoroVoices.find((v) => v.code === slot.code)
              return (
                <div key={i} className="flex items-center gap-3 bg-zinc-800/50 rounded-lg p-3">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0 ${
                    selectedVoice?.gender === 'female' ? 'bg-pink-500/20 text-pink-400' : 'bg-blue-500/20 text-blue-400'
                  }`}>
                    {i + 1}
                  </div>
                  <select
                    value={slot.code}
                    onChange={(e) => {
                      const newSlots = [...blendSlots]
                      newSlots[i].code = e.target.value
                      setBlendSlots(newSlots)
                    }}
                    className="flex-1 px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-xs"
                  >
                    {kokoroVoices.filter((v) => v.language !== 'zh').map((v) => (
                      <option key={v.code} value={v.code}>{v.name}</option>
                    ))}
                  </select>
                  <div className="flex items-center gap-2 w-40">
                    <input
                      type="range" min={0} max={100} value={slot.weight}
                      onChange={(e) => {
                        const newSlots = [...blendSlots]
                        newSlots[i].weight = Number(e.target.value)
                        setBlendSlots(newSlots)
                      }}
                      className="flex-1"
                    />
                    <span className="text-xs text-violet-400 font-mono w-10 text-right">{slot.weight}%</span>
                  </div>
                  {blendSlots.length > 2 && (
                    <button onClick={() => setBlendSlots(blendSlots.filter((_, j) => j !== i))} className="text-zinc-600 hover:text-red-400 p-1">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              )
            })}
          </div>

          {blendSlots.length < 4 && (
            <button
              onClick={() => setBlendSlots([...blendSlots, { code: 'af_bella', weight: 20 }])}
              className="flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300 transition-colors"
            >
              <Plus className="w-3 h-3" /> Add another voice
            </button>
          )}

          {/* Quick presets */}
          <div>
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">Quick Presets</p>
            <div className="flex flex-wrap gap-2">
              {[
                { label: 'Warm Female', slots: [{ code: 'af_heart', weight: 60 }, { code: 'af_bella', weight: 40 }] },
                { label: 'Deep Male', slots: [{ code: 'am_adam', weight: 50 }, { code: 'am_onyx', weight: 50 }] },
                { label: 'British Narrator', slots: [{ code: 'bf_emma', weight: 70 }, { code: 'bf_lily', weight: 30 }] },
                { label: 'Storyteller', slots: [{ code: 'am_puck', weight: 40 }, { code: 'am_michael', weight: 30 }, { code: 'am_liam', weight: 30 }] },
                { label: 'Gentle Female', slots: [{ code: 'af_sky', weight: 50 }, { code: 'af_river', weight: 50 }] },
              ].map((preset) => (
                <button
                  key={preset.label}
                  onClick={() => setBlendSlots(preset.slots)}
                  className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-lg text-[10px] text-zinc-400 hover:text-zinc-200 transition-colors"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          {/* Name + Create */}
          <div className="flex items-center gap-3 pt-2 border-t border-zinc-800">
            <input
              value={blendName}
              onChange={(e) => setBlendName(e.target.value)}
              placeholder="Name your blended voice..."
              className="flex-1 px-4 py-2.5 bg-zinc-800 border border-zinc-700 rounded-xl text-sm focus:outline-none focus:border-violet-500"
            />
            <button
              onClick={handleBlend}
              disabled={blending || !blendName.trim()}
              className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 disabled:from-zinc-700 disabled:to-zinc-700 disabled:opacity-50 rounded-xl text-xs font-medium transition-all shadow-lg shadow-violet-500/10"
            >
              {blending ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Creating...</> : <><Plus className="w-3.5 h-3.5" /> Create Voice</>}
            </button>
          </div>
        </div>
      )}

      {/* My Cloned Voices */}
      {filteredUserVoices.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Mic className="w-4 h-4" /> My Cloned Voices ({filteredUserVoices.length})
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {filteredUserVoices.map((voice) => (
              <div key={voice.id} className="bg-zinc-900 border border-zinc-700 rounded-lg p-4 hover:border-zinc-600 transition-colors">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-violet-500/20 flex items-center justify-center text-violet-400 font-medium">
                    {voice.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-sm truncate">{voice.name}</h3>
                    <p className="text-xs text-zinc-500">{voice.engine} / {voice.language}</p>
                  </div>
                  <button onClick={() => toggleFavorite(voice.id)} className="text-zinc-500 hover:text-yellow-500">
                    <Star className={`w-4 h-4 ${voice.is_favorite ? 'text-yellow-500 fill-yellow-500' : ''}`} />
                  </button>
                </div>
                <div className="flex items-center gap-2 mt-3 pt-3 border-t border-zinc-800">
                  {voice.sample_url && (
                    <button
                      onClick={() => handlePlayPause(voice.id, audioUrl(voice.sample_url!))}
                      className={`flex items-center gap-1 text-xs ${playingId === voice.id ? 'text-violet-400' : 'text-zinc-400 hover:text-zinc-200'}`}
                    >
                      {playingId === voice.id ? <><Pause className="w-3 h-3" /> Pause</> : <><Play className="w-3 h-3" /> Preview</>}
                    </button>
                  )}
                  <span className="text-xs text-zinc-600 ml-auto">{voice.use_count} uses</span>
                  <button
                    onClick={() => { if (confirm(`Delete "${voice.name}"?`)) deleteVoice(voice.id) }}
                    className="text-zinc-600 hover:text-red-400"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Narrator Voice Pack (grouped by language like Kokoro) */}
      {Object.keys(narratorsByLang).length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Volume2 className="w-4 h-4 text-emerald-400" /> Narrator Voices ({filteredNarrators.length})
          </h2>

          {['en', 'en-gb', 'de', 'fr', 'es', 'it', 'pt', 'hi', 'ja'].map((lang) => {
            const langNarrators = narratorsByLang[lang]
            if (!langNarrators || langNarrators.length === 0) return null
            return (
              <div key={lang} className="mb-4">
                <h3 className="text-xs text-zinc-500 mb-2">{langLabels[lang] || lang}</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
                  {langNarrators.map((voice) => {
                    const isFemale = voice.tags?.includes('female') || voice.notes?.includes('female')
                    const gender = isFemale ? 'female' : 'male'
                    const accentTag = voice.tags?.find((t: string) => ['american', 'british', 'nigerian', 'german', 'french', 'spanish', 'italian', 'portuguese', 'hindi', 'japanese'].includes(t))
                    return (
                      <div
                        key={voice.id}
                        onClick={() => handlePreviewNarrator(voice.id, voice.name)}
                        className={`flex items-center gap-3 bg-zinc-900 border rounded-lg px-3 py-2.5 cursor-pointer transition-colors group ${
                          playingId === voice.id ? 'border-emerald-500/50 bg-emerald-500/5' : 'border-zinc-700 hover:border-emerald-500/30'
                        }`}
                      >
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0 ${
                          gender === 'female' ? 'bg-pink-500/20 text-pink-400' : 'bg-blue-500/20 text-blue-400'
                        }`}>
                          {gender === 'female' ? 'F' : 'M'}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium truncate">{voice.name}</p>
                          {accentTag && <p className="text-[10px] text-zinc-600 capitalize">{accentTag}</p>}
                        </div>
                        <div className="flex-shrink-0 p-1.5">
                          {previewingId === voice.id ? (
                            <Loader2 className="w-3.5 h-3.5 text-emerald-400 animate-spin" />
                          ) : playingId === voice.id ? (
                            <Pause className="w-3.5 h-3.5 text-emerald-400" />
                          ) : (
                            <Play className="w-3.5 h-3.5 text-zinc-600 group-hover:text-emerald-400" />
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Kokoro Built-in Voices */}
      <div>
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
          <Volume2 className="w-4 h-4" /> Kokoro Built-in Voices ({filteredKokoro.length})
        </h2>

        {['en', 'en-gb', 'ja', 'es', 'fr', 'hi', 'it', 'pt'].map((lang) => {
          const langVoices = filteredKokoro.filter((v) => v.language === lang)
          if (langVoices.length === 0) return null
          return (
            <div key={lang} className="mb-6">
              <h3 className="text-xs text-zinc-500 mb-2">{langLabels[lang] || lang}</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
                {langVoices.map((voice) => (
                  <div
                    key={voice.code}
                    className="flex items-center gap-3 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2.5 hover:border-zinc-600 transition-colors group"
                  >
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0 ${
                      voice.gender === 'female' ? 'bg-pink-500/20 text-pink-400' : 'bg-blue-500/20 text-blue-400'
                    }`}>
                      {voice.gender === 'female' ? 'F' : 'M'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate">{voice.name}</p>
                    </div>
                    <button
                      onClick={() => handlePreviewKokoro(voice.code)}
                      disabled={previewingId === voice.code}
                      className={`flex-shrink-0 p-1.5 rounded transition-colors ${
                        playingId === voice.code
                          ? 'text-violet-400'
                          : previewingId === voice.code
                          ? 'text-zinc-500'
                          : 'text-zinc-600 hover:text-violet-400 opacity-0 group-hover:opacity-100'
                      }`}
                    >
                      {previewingId === voice.code ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : playingId === voice.code ? (
                        <Pause className="w-3.5 h-3.5" />
                      ) : (
                        <Play className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {filteredUserVoices.length === 0 && filteredNarrators.length === 0 && filteredKokoro.length === 0 && (
        <div className="text-center text-zinc-500 py-16">
          <p>No voices match your search</p>
        </div>
      )}
    </div>
  )
}
