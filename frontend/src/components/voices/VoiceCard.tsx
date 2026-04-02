import { Star, Play, Trash2 } from 'lucide-react'
import type { Voice } from '../../types'

interface VoiceCardProps {
  voice: Voice
  onToggleFavorite: () => void
  onDelete: () => void
  onSelect?: () => void
}

export default function VoiceCard({ voice, onToggleFavorite, onDelete, onSelect }: VoiceCardProps) {
  return (
    <div
      className="bg-zinc-900 border border-zinc-700 rounded-lg p-4 hover:border-zinc-600 cursor-pointer transition-colors"
      onClick={onSelect}
    >
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-full bg-violet-500/20 flex items-center justify-center text-violet-400 font-medium">
          {voice.name.charAt(0).toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-sm truncate">{voice.name}</h3>
          <p className="text-xs text-zinc-500">{voice.engine} / {voice.language}</p>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onToggleFavorite() }}
          className="text-zinc-500 hover:text-yellow-500"
        >
          <Star className={`w-4 h-4 ${voice.is_favorite ? 'text-yellow-500 fill-yellow-500' : ''}`} />
        </button>
      </div>

      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-zinc-800 text-xs">
        {voice.sample_url && (
          <button
            onClick={(e) => { e.stopPropagation(); new Audio(voice.sample_url!).play() }}
            className="flex items-center gap-1 text-zinc-400 hover:text-zinc-200"
          >
            <Play className="w-3 h-3" /> Preview
          </button>
        )}
        <span className="text-zinc-600 ml-auto">Quality: {voice.quality_score}/5</span>
        <span className="text-zinc-600">{voice.use_count} uses</span>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete() }}
          className="text-zinc-600 hover:text-red-400"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>
    </div>
  )
}
