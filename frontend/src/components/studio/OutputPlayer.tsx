import { useEffect, useRef, useState } from 'react'
import { Play, Pause, Download, RefreshCw, Trash2, Loader2 } from 'lucide-react'
import { useStudioStore } from '../../stores/studioStore'
import { apiFetch, audioUrl } from '../../lib/api'

export default function OutputPlayer() {
  const { output } = useStudioStore()
  const audioRef = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [converting, setConverting] = useState<string | null>(null)

  useEffect(() => {
    setPlaying(false)
    setCurrentTime(0)
  }, [output])

  if (!output) return null

  const togglePlay = () => {
    if (!audioRef.current) return
    if (playing) {
      audioRef.current.pause()
    } else {
      audioRef.current.play()
    }
    setPlaying(!playing)
  }

  const formatTime = (s: number) => {
    const mins = Math.floor(s / 60)
    const secs = Math.floor(s % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const handleDownloadFormat = async (format: string) => {
    setConverting(format)
    try {
      const result = await apiFetch<{ audio_url: string; filename: string }>('/audio/convert', {
        method: 'POST',
        body: JSON.stringify({ audio_url: output.audio_url, format }),
      })
      const a = document.createElement('a')
      a.href = audioUrl(result.audio_url)
      a.download = result.filename
      a.click()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Conversion failed')
    } finally {
      setConverting(null)
    }
  }

  const progress = output.duration > 0 ? (currentTime / output.duration) * 100 : 0

  return (
    <div className="bg-zinc-800 rounded-lg border border-zinc-700 p-4">
      <audio
        ref={audioRef}
        src={audioUrl(output.audio_url)}
        onTimeUpdate={() => setCurrentTime(audioRef.current?.currentTime || 0)}
        onEnded={() => setPlaying(false)}
      />

      {/* Waveform-like progress bar */}
      <div className="flex items-center gap-3 mb-3">
        <button
          onClick={togglePlay}
          className="w-10 h-10 flex items-center justify-center rounded-full bg-violet-500 hover:bg-violet-600 transition-colors"
        >
          {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
        </button>

        <div className="flex-1">
          <div
            className="h-2 bg-zinc-700 rounded-full cursor-pointer"
            onClick={(e) => {
              if (!audioRef.current) return
              const rect = e.currentTarget.getBoundingClientRect()
              const pct = (e.clientX - rect.left) / rect.width
              audioRef.current.currentTime = pct * output.duration
            }}
          >
            <div
              className="h-full bg-violet-500 rounded-full transition-all duration-100"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <span className="text-xs text-zinc-500 font-mono min-w-[80px] text-right">
          {formatTime(currentTime)} / {formatTime(output.duration)}
        </span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Download formats */}
        <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Download:</span>
        <a
          href={audioUrl(output.audio_url)}
          download={`frenzai_${Date.now()}.wav`}
          className="flex items-center gap-1 px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-md"
        >
          <Download className="w-3 h-3" /> WAV
        </a>
        <button
          onClick={() => handleDownloadFormat('mp3')}
          disabled={converting !== null}
          className="flex items-center gap-1 px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50 rounded-md"
        >
          {converting === 'mp3' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />} MP3
        </button>
        <button
          onClick={() => handleDownloadFormat('mp3-acx')}
          disabled={converting !== null}
          className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-600/20 text-green-400 hover:bg-green-600/30 disabled:opacity-50 rounded-md border border-green-500/20"
        >
          {converting === 'mp3-acx' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />} MP3 (ACX)
        </button>
        <button
          onClick={() => handleDownloadFormat('lpf')}
          disabled={converting !== null}
          className="flex items-center gap-1 px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50 rounded-md"
        >
          {converting === 'lpf' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />} LPF
        </button>

        <div className="flex items-center gap-2 ml-auto">
          <button
            onClick={() => useStudioStore.getState().generate()}
            className="flex items-center gap-1 px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-md text-zinc-300"
          >
            <RefreshCw className="w-3 h-3" /> Regenerate
          </button>
          <button
            onClick={() => {
              if (audioRef.current) {
                audioRef.current.pause()
              }
              useStudioStore.setState({ output: null })
            }}
            className="flex items-center gap-1 px-3 py-1.5 text-xs bg-zinc-700 hover:bg-red-500/20 hover:text-red-400 rounded-md text-zinc-400"
          >
            <Trash2 className="w-3 h-3" /> Delete
          </button>
          <span className="text-xs text-zinc-600">
            {output.generation_time}s
          </span>
        </div>
      </div>
    </div>
  )
}
