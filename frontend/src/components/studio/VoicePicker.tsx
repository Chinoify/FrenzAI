import { useEffect, useState } from 'react'
import { ChevronDown, Star, Plus, User, Mic, Search } from 'lucide-react'
import { useVoiceStore } from '../../stores/voiceStore'
import { useStudioStore } from '../../stores/studioStore'
import { useProjectStore } from '../../stores/projectStore'
import { useNavigate } from 'react-router-dom'

export default function VoicePicker() {
  const { voices, fetchVoices } = useVoiceStore()
  const { selectedVoiceId, setSelectedVoiceId, setSelectedModel } = useStudioStore()
  const { kokoroVoices, fetchKokoroVoices } = useProjectStore()
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    fetchVoices()
    fetchKokoroVoices()
  }, [fetchVoices, fetchKokoroVoices])

  const selectedVoice = voices.find((v) => v.id === selectedVoiceId)
  // Check if it's a kokoro voice selection (stored as kokoro:voice_code)
  const selectedKokoroVoice = kokoroVoices.find((v) => v.code === selectedVoiceId)
  const displayName = selectedVoice ? selectedVoice.name : selectedKokoroVoice ? selectedKokoroVoice.name : 'Default Voice (Heart)'

  const filteredKokoro = kokoroVoices.filter((v) =>
    !search || v.name.toLowerCase().includes(search.toLowerCase()) ||
    v.language.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg hover:border-zinc-600 min-w-[220px]"
      >
        <User className="w-4 h-4 text-zinc-400" />
        <span className="text-sm flex-1 text-left truncate">
          {displayName}
        </span>
        <ChevronDown className="w-4 h-4 text-zinc-500" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute top-full left-0 mt-1 w-80 bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl z-50 max-h-[400px] flex flex-col">
            {/* Search */}
            <div className="p-2 border-b border-zinc-700">
              <div className="flex items-center gap-2 px-2 py-1.5 bg-zinc-900 rounded-md">
                <Search className="w-3 h-3 text-zinc-500" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search voices..."
                  className="bg-transparent text-xs flex-1 focus:outline-none"
                  autoFocus
                />
              </div>
            </div>

            <div className="overflow-y-auto flex-1">
              {/* Default option */}
              <button
                onClick={() => { setSelectedVoiceId(null); setSelectedModel('kokoro'); setOpen(false); setSearch('') }}
                className={`w-full flex items-center gap-3 px-3 py-2 text-sm hover:bg-zinc-700 ${
                  !selectedVoiceId ? 'bg-zinc-700 text-violet-400' : 'text-zinc-300'
                }`}
              >
                <div className="w-7 h-7 rounded-full bg-zinc-600 flex items-center justify-center">
                  <User className="w-3.5 h-3.5" />
                </div>
                <div className="text-left">
                  <div className="text-xs font-medium">Default Voice (Heart)</div>
                  <div className="text-[10px] text-zinc-500">Kokoro flagship</div>
                </div>
              </button>

              {/* Custom/Cloned Voices */}
              {voices.length > 0 && (
                <>
                  <div className="px-3 py-1.5 text-[10px] text-zinc-500 uppercase tracking-wider bg-zinc-900/50">
                    🎤 My Cloned Voices
                  </div>
                  {voices.filter((v) => !search || v.name.toLowerCase().includes(search.toLowerCase())).map((voice) => (
                    <button
                      key={voice.id}
                      onClick={() => { setSelectedVoiceId(voice.id); setSelectedModel(voice.engine || 'chatterbox'); setOpen(false); setSearch('') }}
                      className={`w-full flex items-center gap-3 px-3 py-2 text-sm hover:bg-zinc-700 ${
                        selectedVoiceId === voice.id ? 'bg-zinc-700 text-violet-400' : 'text-zinc-300'
                      }`}
                    >
                      <div className="w-7 h-7 rounded-full bg-violet-500/20 flex items-center justify-center text-violet-400 font-medium text-[10px]">
                        {voice.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="flex-1 text-left">
                        <div className="flex items-center gap-1 text-xs">
                          {voice.name}
                          {voice.is_favorite && <Star className="w-2.5 h-2.5 text-yellow-500 fill-yellow-500" />}
                        </div>
                        <div className="text-[10px] text-zinc-500">{voice.engine} / {voice.language}</div>
                      </div>
                    </button>
                  ))}
                </>
              )}

              {/* Kokoro Voices by language group */}
              {['en', 'en-gb', 'ja', 'es', 'fr', 'hi', 'it', 'pt'].map((lang) => {
                const langVoices = filteredKokoro.filter((v) => v.language === lang)
                if (langVoices.length === 0) return null
                const langLabels: Record<string, string> = {
                  'en': '🇺🇸 English (US)', 'en-gb': '🇬🇧 English (UK)', 'ja': '🇯🇵 Japanese',
                  'es': '🇪🇸 Spanish', 'fr': '🇫🇷 French',
                  'hi': '🇮🇳 Hindi', 'it': '🇮🇹 Italian', 'pt': '🇧🇷 Portuguese',
                }
                return (
                  <div key={lang}>
                    <div className="px-3 py-1.5 text-[10px] text-zinc-500 uppercase tracking-wider bg-zinc-900/50">
                      {langLabels[lang] || lang}
                    </div>
                    {langVoices.map((voice) => (
                      <button
                        key={voice.code}
                        onClick={() => { setSelectedVoiceId(voice.code); setSelectedModel('kokoro'); setOpen(false); setSearch('') }}
                        className={`w-full flex items-center gap-3 px-3 py-1.5 text-sm hover:bg-zinc-700 ${
                          selectedVoiceId === voice.code ? 'bg-zinc-700 text-violet-400' : 'text-zinc-300'
                        }`}
                      >
                        <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-medium ${
                          voice.gender === 'female' ? 'bg-pink-500/20 text-pink-400' : 'bg-blue-500/20 text-blue-400'
                        }`}>
                          {voice.gender === 'female' ? 'F' : 'M'}
                        </div>
                        <div className="text-left">
                          <div className="text-xs">{voice.name}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                )
              })}
            </div>

            <button
              onClick={() => { setOpen(false); setSearch(''); navigate('/clone') }}
              className="w-full flex items-center gap-3 px-3 py-2 text-sm text-violet-400 hover:bg-zinc-700 border-t border-zinc-700"
            >
              <Plus className="w-4 h-4" />
              <span>Clone New Voice</span>
            </button>
          </div>
        </>
      )}
    </div>
  )
}
