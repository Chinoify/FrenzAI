import type { Voice } from '../../types'
import VoiceCard from './VoiceCard'

interface VoiceGridProps {
  voices: Voice[]
  onToggleFavorite: (id: string) => void
  onDelete: (id: string) => void
  onSelect?: (id: string) => void
}

export default function VoiceGrid({ voices, onToggleFavorite, onDelete, onSelect }: VoiceGridProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {voices.map((voice) => (
        <VoiceCard
          key={voice.id}
          voice={voice}
          onToggleFavorite={() => onToggleFavorite(voice.id)}
          onDelete={() => onDelete(voice.id)}
          onSelect={onSelect ? () => onSelect(voice.id) : undefined}
        />
      ))}
    </div>
  )
}
