import { useEffect, useRef, useState } from 'react'
import { Play, Pause } from 'lucide-react'

interface WaveformPlayerProps {
  audioUrl: string
  height?: number
}

export default function WaveformPlayer({ audioUrl, height = 48 }: WaveformPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [duration, setDuration] = useState(0)

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
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  return (
    <div className="flex items-center gap-3">
      <audio
        ref={audioRef}
        src={audioUrl}
        onLoadedMetadata={() => setDuration(audioRef.current?.duration || 0)}
        onTimeUpdate={() => {
          const cur = audioRef.current?.currentTime || 0
          setProgress(duration > 0 ? (cur / duration) * 100 : 0)
        }}
        onEnded={() => setPlaying(false)}
      />
      <button
        onClick={togglePlay}
        className="w-8 h-8 flex items-center justify-center rounded-full bg-violet-500 hover:bg-violet-600 flex-shrink-0"
      >
        {playing ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3 ml-0.5" />}
      </button>
      <div
        className="flex-1 bg-zinc-700 rounded-full cursor-pointer"
        style={{ height: 4 }}
        onClick={(e) => {
          if (!audioRef.current || !duration) return
          const rect = e.currentTarget.getBoundingClientRect()
          audioRef.current.currentTime = ((e.clientX - rect.left) / rect.width) * duration
        }}
      >
        <div className="h-full bg-violet-500 rounded-full" style={{ width: `${progress}%` }} />
      </div>
      <span className="text-xs text-zinc-500 font-mono min-w-[40px]">{formatTime(duration)}</span>
    </div>
  )
}
