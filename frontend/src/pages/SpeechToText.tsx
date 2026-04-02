import { useState, useRef, useCallback } from 'react'
import { Upload, Mic, MicOff, Copy, Send, FileText, Loader2, Download } from 'lucide-react'
import { apiFetch, apiUpload, audioUrl, BACKEND_URL } from '../lib/api'
import { useNavigate } from 'react-router-dom'

export default function SpeechToText() {
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [progress, setProgress] = useState('')
  const [transcript, setTranscript] = useState('')
  const [segments, setSegments] = useState<{ start_sec: number; end_sec: number; text: string }[]>([])
  const [language, setLanguage] = useState('auto')
  const [modelSize, setModelSize] = useState('base')
  const [editing, setEditing] = useState(false)
  const [showTimestamps, setShowTimestamps] = useState(false)
  const [stats, setStats] = useState<{ word_count: number; duration_sec: number; processing_time: number } | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }, [])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) setFile(f)
  }, [])

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data)
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/wav' })
        setFile(new File([blob], 'recording.wav', { type: 'audio/wav' }))
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

  const handleTranscribe = async () => {
    if (!file) return
    setTranscribing(true)
    setTranscript('')
    setSegments([])
    setProgress('Uploading...')

    try {
      // Use streaming endpoint for real-time feedback
      const form = new FormData()
      form.append('file', file)
      form.append('language', language)
      form.append('model_size', modelSize)

      const res = await fetch(`${BACKEND_URL}/api/stt/transcribe-stream`, {
        method: 'POST',
        body: form,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Transcription failed' }))
        throw new Error(err.detail)
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      const allSegments: typeof segments = []
      const allText: string[] = []

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
              if (data.status === 'loading') setProgress('Loading audio...')
              else if (data.status === 'transcribing') setProgress(`Transcribing (${data.language})...`)
              else if (data.status === 'segment') {
                allSegments.push({ start_sec: data.start, end_sec: data.end, text: data.text })
                allText.push(data.text)
                setSegments([...allSegments])
                setTranscript(allText.join(' '))
                setProgress(`Transcribing... ${allText.length} segments`)
              } else if (data.status === 'done') {
                setTranscript(data.text)
                setStats({ word_count: data.word_count, duration_sec: 0, processing_time: 0 })
              } else if (data.status === 'error') {
                throw new Error(data.message)
              }
            } catch (e) {
              if (e instanceof SyntaxError) continue
              throw e
            }
          }
        }
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Transcription failed')
    } finally {
      setTranscribing(false)
      setProgress('')
    }
  }

  const copyToClipboard = () => {
    navigator.clipboard.writeText(transcript)
  }

  const sendToStudio = () => {
    // Store transcript in sessionStorage for Studio to pick up
    sessionStorage.setItem('stt_transcript', transcript)
    navigate('/')
  }

  const exportTxt = () => {
    const blob = new Blob([transcript], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'transcript.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  const exportSrt = () => {
    const srt = segments.map((seg, i) => {
      const formatTime = (s: number) => {
        const h = Math.floor(s / 3600)
        const m = Math.floor((s % 3600) / 60)
        const sec = Math.floor(s % 60)
        const ms = Math.round((s % 1) * 1000)
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`
      }
      return `${i + 1}\n${formatTime(seg.start_sec)} --> ${formatTime(seg.end_sec)}\n${seg.text}\n`
    }).join('\n')
    const blob = new Blob([srt], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'transcript.srt'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-xl font-semibold">Speech to Text</h1>

      {/* Input Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* File Upload */}
        <div
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
            file ? 'border-violet-500 bg-violet-500/5' : 'border-zinc-700 hover:border-zinc-500'
          }`}
          onDrop={handleFileDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*,.mp3,.wav,.m4a,.ogg,.flac,.mp4"
            onChange={handleFileSelect}
            className="hidden"
          />
          <Upload className="w-8 h-8 mx-auto mb-3 text-zinc-500" />
          {file ? (
            <div>
              <p className="text-sm font-medium">{file.name}</p>
              <p className="text-xs text-zinc-500 mt-1">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
            </div>
          ) : (
            <div>
              <p className="text-sm text-zinc-400">Drop audio file here or click to browse</p>
              <p className="text-xs text-zinc-600 mt-1">MP3, WAV, M4A, OGG, FLAC</p>
            </div>
          )}
        </div>

        {/* Microphone */}
        <div className="border border-zinc-700 rounded-xl p-8 text-center">
          <button
            onClick={recording ? stopRecording : startRecording}
            className={`w-16 h-16 mx-auto mb-3 rounded-full flex items-center justify-center transition-colors ${
              recording
                ? 'bg-red-500 hover:bg-red-600 animate-pulse'
                : 'bg-zinc-700 hover:bg-zinc-600'
            }`}
          >
            {recording ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
          </button>
          <p className="text-sm text-zinc-400">
            {recording ? 'Recording... Click to stop' : 'Record from microphone'}
          </p>
        </div>
      </div>

      {/* Options */}
      <div className="flex items-center gap-4">
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm"
        >
          <option value="auto">Auto-detect language</option>
          <option value="en">English</option>
          <option value="es">Spanish</option>
          <option value="fr">French</option>
          <option value="de">German</option>
          <option value="ja">Japanese</option>
          <option value="zh">Chinese</option>
          <option value="ko">Korean</option>
          <option value="pt">Portuguese</option>
        </select>

        <select
          value={modelSize}
          onChange={(e) => setModelSize(e.target.value)}
          className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm"
        >
          <option value="tiny">Tiny (fastest)</option>
          <option value="base">Base (balanced)</option>
          <option value="small">Small (better)</option>
          <option value="medium">Medium (high accuracy)</option>
          <option value="large-v3">Large V3 (best)</option>
        </select>

        <button
          onClick={handleTranscribe}
          disabled={!file || transcribing}
          className="flex items-center gap-2 px-4 py-2 bg-violet-500 hover:bg-violet-600 disabled:bg-zinc-700 rounded-lg text-sm font-medium transition-colors"
        >
          {transcribing ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
          {transcribing ? progress || 'Transcribing...' : 'Transcribe'}
        </button>
      </div>

      {/* Output */}
      {transcript && (
        <div className="space-y-3">
          {/* Toolbar */}
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setEditing(!editing)}
              className={`px-3 py-1.5 text-xs rounded-md ${editing ? 'bg-violet-500' : 'bg-zinc-700 hover:bg-zinc-600'}`}
            >
              {editing ? 'Save' : 'Edit'}
            </button>
            <button onClick={copyToClipboard} className="flex items-center gap-1 px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-md">
              <Copy className="w-3 h-3" /> Copy
            </button>
            <button onClick={sendToStudio} className="flex items-center gap-1 px-3 py-1.5 text-xs bg-violet-500 hover:bg-violet-600 rounded-md">
              <Send className="w-3 h-3" /> Send to Studio
            </button>
            <button onClick={exportTxt} className="flex items-center gap-1 px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-md">
              <Download className="w-3 h-3" /> .txt
            </button>
            {segments.length > 0 && (
              <button onClick={exportSrt} className="flex items-center gap-1 px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-md">
                <Download className="w-3 h-3" /> .srt
              </button>
            )}
            <button
              onClick={() => setShowTimestamps(!showTimestamps)}
              className={`px-3 py-1.5 text-xs rounded-md ${showTimestamps ? 'bg-blue-500/20 text-blue-400' : 'bg-zinc-700 hover:bg-zinc-600'}`}
            >
              Timestamps
            </button>
            <span className="ml-auto text-xs text-zinc-500">
              {transcript.split(/\s+/).length} words / {transcript.length} chars
            </span>
          </div>

          {/* Text area */}
          {editing ? (
            <textarea
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              className="w-full h-64 px-4 py-3 bg-zinc-900 border border-zinc-700 rounded-lg text-sm leading-relaxed resize-y focus:outline-none focus:border-violet-500 font-mono"
            />
          ) : (
            <div className="w-full min-h-[200px] px-4 py-3 bg-zinc-900 border border-zinc-700 rounded-lg text-sm leading-relaxed">
              {showTimestamps && segments.length > 0 ? (
                segments.map((seg, i) => (
                  <span key={i}>
                    <span className="text-[10px] text-violet-400 font-mono">[{Math.floor(seg.start_sec / 60)}:{(seg.start_sec % 60).toFixed(0).padStart(2, '0')}]</span>
                    {' '}{seg.text}{' '}
                  </span>
                ))
              ) : (
                <p className="text-zinc-300 whitespace-pre-wrap">{transcript}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
