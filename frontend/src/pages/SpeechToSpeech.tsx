import { useState, useRef } from 'react'
import { ArrowRightLeft, Upload, Mic, Loader2, Play, Pause, Download, Send } from 'lucide-react'
import { useVoiceStore } from '../stores/voiceStore'
import { useProjectStore } from '../stores/projectStore'
import { apiFetch, apiUpload, audioUrl, BACKEND_URL } from '../lib/api'
import { useNavigate } from 'react-router-dom'
import { useEffect } from 'react'

export default function SpeechToSpeech() {
  const navigate = useNavigate()
  const { voices, fetchVoices } = useVoiceStore()
  const { kokoroVoices, fetchKokoroVoices } = useProjectStore()
  const [file, setFile] = useState<File | null>(null)
  const [recording, setRecording] = useState(false)
  const [targetVoice, setTargetVoice] = useState('')
  const [model, setModel] = useState('kokoro')
  const [processing, setProcessing] = useState(false)
  const [result, setResult] = useState<{ transcript: string; audio_url: string; input_duration_ms: number; output_duration_ms: number } | null>(null)
  const [playing, setPlaying] = useState<'input' | 'output' | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  useEffect(() => {
    fetchVoices()
    fetchKokoroVoices()
  }, [fetchVoices, fetchKokoroVoices])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) setFile(e.target.files[0])
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0])
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data)
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setFile(new File([blob], 'recording.webm', { type: 'audio/webm' }))
        stream.getTracks().forEach((t) => t.stop())
      }
      recorder.start()
      mediaRecorderRef.current = recorder
      setRecording(true)
    } catch {
      alert('Microphone access denied')
    }
  }

  const stopRecording = () => {
    mediaRecorderRef.current?.stop()
    setRecording(false)
  }

  const handleConvert = async () => {
    if (!file) return
    setProcessing(true)
    setResult(null)
    try {
      const form = new FormData()
      form.append('audio_file', file)
      form.append('target_voice_id', targetVoice || 'af_heart')
      form.append('model', model)
      form.append('language', 'en')
      const data = await apiUpload<any>('/s2s/convert', form)
      setResult(data)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Conversion failed')
    } finally {
      setProcessing(false)
    }
  }

  const playAudio = (url: string, type: 'input' | 'output') => {
    if (playing === type) {
      audioRef.current?.pause()
      setPlaying(null)
      return
    }
    audioRef.current?.pause()
    const audio = new Audio(audioUrl(url))
    audio.onended = () => setPlaying(null)
    audio.play()
    audioRef.current = audio
    setPlaying(type)
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Voice Swap (Speech-to-Speech)</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Upload or record audio in any voice, and FrenzAI will re-render it in your chosen voice.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Input */}
        <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-4 space-y-4">
          <h2 className="text-sm font-medium text-zinc-300">Source Audio</h2>

          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-zinc-700 rounded-lg p-6 text-center hover:border-violet-500/50 transition-colors"
          >
            {file ? (
              <div>
                <p className="text-sm text-violet-400">{file.name}</p>
                <p className="text-xs text-zinc-500 mt-1">{(file.size / 1024).toFixed(0)} KB</p>
                <button onClick={() => setFile(null)} className="text-xs text-red-400 mt-2 hover:underline">Remove</button>
              </div>
            ) : (
              <>
                <Upload className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
                <p className="text-xs text-zinc-500">Drop audio file or click to browse</p>
                <input type="file" accept="audio/*" onChange={handleFileSelect} className="hidden" id="s2s-upload" />
                <label htmlFor="s2s-upload" className="text-xs text-violet-400 cursor-pointer hover:underline">Browse files</label>
              </>
            )}
          </div>

          <div className="flex gap-2">
            <button
              onClick={recording ? stopRecording : startRecording}
              className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                recording ? 'bg-red-500 hover:bg-red-600' : 'bg-zinc-800 hover:bg-zinc-700'
              }`}
            >
              <Mic className="w-3 h-3" />
              {recording ? 'Stop Recording' : 'Record'}
            </button>
          </div>
        </div>

        {/* Settings */}
        <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-4 space-y-4 flex flex-col justify-center">
          <h2 className="text-sm font-medium text-zinc-300">Target Voice</h2>

          <select
            value={targetVoice}
            onChange={(e) => setTargetVoice(e.target.value)}
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm"
          >
            <option value="">Default (Heart)</option>
            {voices.length > 0 && (
              <optgroup label="My Cloned Voices">
                {voices.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
              </optgroup>
            )}
            <optgroup label="Kokoro Voices">
              {kokoroVoices.map((v) => <option key={v.code} value={v.code}>{v.name}</option>)}
            </optgroup>
          </select>

          <div className="flex items-center justify-center py-4">
            <ArrowRightLeft className="w-10 h-10 text-violet-500" />
          </div>

          <button
            onClick={handleConvert}
            disabled={!file || processing}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-violet-500 hover:bg-violet-600 disabled:bg-zinc-700 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
          >
            {processing ? <><Loader2 className="w-4 h-4 animate-spin" /> Converting...</> : <><ArrowRightLeft className="w-4 h-4" /> Convert Voice</>}
          </button>
        </div>

        {/* Output */}
        <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-4 space-y-4">
          <h2 className="text-sm font-medium text-zinc-300">Output</h2>

          {result ? (
            <div className="space-y-3">
              <div className="bg-zinc-800 rounded-lg p-3">
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Transcript</p>
                <p className="text-sm text-zinc-300 leading-relaxed">{result.transcript}</p>
              </div>

              <button
                onClick={() => playAudio(result.audio_url, 'output')}
                className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  playing === 'output' ? 'bg-violet-500/20 text-violet-400' : 'bg-zinc-800 hover:bg-zinc-700'
                }`}
              >
                {playing === 'output' ? <><Pause className="w-3 h-3" /> Playing</> : <><Play className="w-3 h-3" /> Play Output</>}
              </button>

              <div className="flex gap-2">
                <a
                  href={audioUrl(result.audio_url)}
                  download="voice_swap_output.wav"
                  className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-xs"
                >
                  <Download className="w-3 h-3" /> Download
                </a>
                <button
                  onClick={() => {
                    navigate('/')
                    // The studio store would need to be populated
                  }}
                  className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-xs"
                >
                  <Send className="w-3 h-3" /> Send to Studio
                </button>
              </div>

              <div className="text-[10px] text-zinc-600 space-y-0.5">
                <p>Input: {(result.input_duration_ms / 1000).toFixed(1)}s</p>
                <p>Output: {(result.output_duration_ms / 1000).toFixed(1)}s</p>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-40 text-zinc-600">
              <div className="text-center">
                <ArrowRightLeft className="w-8 h-8 mx-auto mb-2" />
                <p className="text-xs">Output will appear here</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
