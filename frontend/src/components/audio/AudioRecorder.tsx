import { Mic, Square } from 'lucide-react'
import { useAudioRecorder } from '../../hooks/useAudioRecorder'

interface AudioRecorderProps {
  onRecorded: (blob: Blob) => void
}

export default function AudioRecorder({ onRecorded }: AudioRecorderProps) {
  const { recording, duration, audioBlob, start, stop } = useAudioRecorder()

  const handleStop = () => {
    stop()
    // audioBlob is set async in onstop
    setTimeout(() => {
      if (audioBlob) onRecorded(audioBlob)
    }, 200)
  }

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  return (
    <div className="flex items-center gap-3">
      {recording ? (
        <>
          <button
            onClick={handleStop}
            className="flex items-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-600 rounded-lg text-sm"
          >
            <Square className="w-4 h-4" /> Stop
          </button>
          <span className="text-sm text-red-400 animate-pulse">{formatTime(duration)}</span>
        </>
      ) : (
        <button
          onClick={start}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg text-sm"
        >
          <Mic className="w-4 h-4" /> Record
        </button>
      )}
    </div>
  )
}
