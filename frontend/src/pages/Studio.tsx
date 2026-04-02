import { ChevronDown, Sparkles, Loader2 } from 'lucide-react'
import TextEditor from '../components/studio/TextEditor'
import VoicePicker from '../components/studio/VoicePicker'
import ParamControls from '../components/studio/ParamControls'
import OutputPlayer from '../components/studio/OutputPlayer'
import { useStudioStore } from '../stores/studioStore'
import { useAppStore } from '../stores/appStore'
import { useVoiceStore } from '../stores/voiceStore'
import { LANGUAGES } from '../lib/constants'

export default function Studio() {
  const { selectedModel, setSelectedModel, selectedVoiceId, language, setLanguage, error, generating, generate, text } = useStudioStore()
  const { models } = useAppStore()
  const { voices } = useVoiceStore()

  // Check if a cloned voice is selected (UUID, not a kokoro code)
  const isClonedVoice = selectedVoiceId && voices.some((v) => v.id === selectedVoiceId)
  const CLONING_ENGINES = ['chatterbox', 'f5tts', 'qwen3tts', 'fishspeech', 'fish-speech']

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Text to Speech</h1>
        <p className="text-sm text-zinc-500 mt-1">Type or paste text, choose a voice, and generate natural speech.</p>
      </div>

      {/* Controls toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <VoicePicker />

        <div className="relative">
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="appearance-none px-4 py-2.5 pr-9 bg-zinc-900 border border-zinc-800 rounded-xl text-sm cursor-pointer hover:border-zinc-600 focus:outline-none focus:border-violet-500 transition-colors"
          >
            {isClonedVoice ? (
              models.filter((m) => CLONING_ENGINES.includes(m.name)).length > 0
                ? models.filter((m) => CLONING_ENGINES.includes(m.name)).map((m) => (
                    <option key={m.name} value={m.name}>{m.display_name} (Clone)</option>
                  ))
                : <option value="chatterbox">Chatterbox (Clone)</option>
            ) : models.length > 0 ? (
              models.map((m) => (
                <option key={m.name} value={m.name}>{m.display_name}</option>
              ))
            ) : (
              <option value="kokoro">Kokoro</option>
            )}
          </select>
          <ChevronDown className="w-4 h-4 text-zinc-500 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        </div>

        <div className="relative">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="appearance-none px-4 py-2.5 pr-9 bg-zinc-900 border border-zinc-800 rounded-xl text-sm cursor-pointer hover:border-zinc-600 focus:outline-none focus:border-violet-500 transition-colors"
          >
            {LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>{l.name}</option>
            ))}
          </select>
          <ChevronDown className="w-4 h-4 text-zinc-500 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-3 bg-red-500/5 border border-red-500/20 rounded-xl text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Text editor */}
      <TextEditor />

      {/* Advanced params (collapsed by default) */}
      <ParamControls />

      {/* Generate button */}
      <button
        onClick={generate}
        disabled={generating || !text.trim()}
        className="w-full flex items-center justify-center gap-2 px-6 py-3.5 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 disabled:from-zinc-700 disabled:to-zinc-700 disabled:opacity-50 rounded-xl text-sm font-medium transition-all shadow-lg shadow-violet-500/10 hover:shadow-violet-500/20"
      >
        {generating ? (
          <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
        ) : (
          <><Sparkles className="w-4 h-4" /> Generate Speech</>
        )}
      </button>

      {/* Output */}
      <OutputPlayer />
    </div>
  )
}
