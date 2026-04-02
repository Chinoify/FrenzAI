import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { useStudioStore } from '../../stores/studioStore'
import type { TTSParams } from '../../types'

const SLIDERS: { key: keyof TTSParams; label: string; min: number; max: number; step: number }[] = [
  { key: 'speed', label: 'Speed', min: 0.25, max: 4.0, step: 0.05 },
  { key: 'stability', label: 'Stability', min: 0, max: 1, step: 0.05 },
  { key: 'clarity', label: 'Clarity', min: 0, max: 1, step: 0.05 },
  { key: 'steps', label: 'Steps', min: 1, max: 50, step: 1 },
]

export default function ParamControls() {
  const { params, setParam } = useStudioStore()
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="bg-zinc-800 rounded-lg border border-zinc-700">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200"
      >
        <span>Parameters</span>
        {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {expanded && (
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 px-4 pb-4">
          {SLIDERS.map(({ key, label, min, max, step }) => (
            <div key={key} className="flex flex-col gap-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-400">{label}</span>
                <span className="text-zinc-300 font-mono">
                  {key === 'speed' ? `${params[key].toFixed(2)}x` : params[key]}
                </span>
              </div>
              <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={params[key]}
                onChange={(e) => setParam(key, parseFloat(e.target.value))}
                className="w-full h-1 bg-zinc-600 rounded-full appearance-none cursor-pointer accent-violet-500"
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
