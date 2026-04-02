import { useEffect, useState, useRef } from 'react'
import { Clock, Play, Pause, Trash2, Download } from 'lucide-react'
import { apiFetch, audioUrl } from '../lib/api'
import type { HistoryEntry } from '../types'

export default function History() {
  const [entries, setEntries] = useState<HistoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [playingId, setPlayingId] = useState<number | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    apiFetch<HistoryEntry[]>('/history')
      .then(setEntries)
      .finally(() => setLoading(false))
  }, [])

  const handlePlayPause = (entry: HistoryEntry) => {
    if (!entry.audio_url) return

    if (playingId === entry.id) {
      // Currently playing this entry — pause it
      audioRef.current?.pause()
      setPlayingId(null)
      return
    }

    // Stop any currently playing audio
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }

    const audio = new Audio(audioUrl(entry.audio_url))
    audio.onended = () => {
      setPlayingId(null)
      audioRef.current = null
    }
    audio.onerror = () => {
      setPlayingId(null)
      audioRef.current = null
    }
    audio.play()
    audioRef.current = audio
    setPlayingId(entry.id)
  }

  const handleDelete = async (id: number) => {
    // Stop if we're playing the one being deleted
    if (playingId === id) {
      audioRef.current?.pause()
      audioRef.current = null
      setPlayingId(null)
    }
    await apiFetch(`/history/${id}`, { method: 'DELETE' })
    setEntries((e) => e.filter((entry) => entry.id !== id))
  }

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Generation History</h1>

      {entries.length === 0 && !loading ? (
        <div className="text-center text-zinc-500 py-16">
          <Clock className="w-12 h-12 mx-auto mb-3 text-zinc-700" />
          <p>No generations yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map((entry) => (
            <div
              key={entry.id}
              className="flex items-center gap-4 p-3 bg-zinc-900 border border-zinc-700 rounded-lg"
            >
              {entry.audio_url && (
                <button
                  onClick={() => handlePlayPause(entry)}
                  className={`w-8 h-8 flex items-center justify-center rounded-full transition-colors ${
                    playingId === entry.id
                      ? 'bg-violet-500/20 text-violet-400'
                      : 'bg-zinc-800 hover:bg-violet-500/20 text-zinc-400 hover:text-violet-400'
                  }`}
                >
                  {playingId === entry.id ? (
                    <Pause className="w-3 h-3" />
                  ) : (
                    <Play className="w-3 h-3" />
                  )}
                </button>
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{entry.text_preview}</p>
                <p className="text-xs text-zinc-500">
                  {entry.voice_name} / {entry.model}
                  {entry.duration_seconds && ` / ${entry.duration_seconds}s`}
                </p>
              </div>
              <span className="text-xs text-zinc-600">
                {new Date(entry.created_at).toLocaleString()}
              </span>
              {entry.audio_url && (
                <a
                  href={audioUrl(entry.audio_url)}
                  download={`frenzai_${entry.id}.wav`}
                  className="text-zinc-600 hover:text-violet-400"
                  title="Download"
                >
                  <Download className="w-3 h-3" />
                </a>
              )}
              <button onClick={() => handleDelete(entry.id)} className="text-zinc-600 hover:text-red-400" title="Delete">
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
