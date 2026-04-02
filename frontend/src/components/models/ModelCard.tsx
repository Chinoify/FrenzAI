import { Cpu } from 'lucide-react'
import type { ModelInfo } from '../../types'

interface ModelCardProps {
  model: ModelInfo
  isActive: boolean
  onLoad: () => void
  onUnload: () => void
}

export default function ModelCard({ model, isActive, onLoad, onUnload }: ModelCardProps) {
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-4">
      <div className="flex items-start justify-between mb-2">
        <div>
          <h3 className="font-medium">{model.display_name}</h3>
          <p className="text-xs text-zinc-500 mt-1">{model.description}</p>
        </div>
        {model.is_loaded && (
          <span className="px-2 py-0.5 text-xs bg-green-500/10 text-green-400 rounded-full">Active</span>
        )}
      </div>

      <div className="flex items-center gap-4 text-xs text-zinc-500 mb-3">
        <span>{model.languages.slice(0, 5).join(', ')}{model.languages.length > 5 ? '...' : ''}</span>
        <span>{model.model_size_mb}MB</span>
        <span>VRAM: {model.vram_required_mb}MB</span>
        <span className="text-zinc-600">{model.license}</span>
      </div>

      <div className="flex items-center gap-2">
        {!model.is_loaded && (
          <button onClick={onLoad} className="flex items-center gap-1 px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-md">
            <Cpu className="w-3 h-3" /> Load
          </button>
        )}
        {model.is_loaded && (
          <button onClick={onUnload} className="flex items-center gap-1 px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-md">
            Unload
          </button>
        )}
      </div>
    </div>
  )
}
