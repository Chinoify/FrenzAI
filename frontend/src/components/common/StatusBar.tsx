import { Cpu, HardDrive, Zap } from 'lucide-react'
import { useAppStore } from '../../stores/appStore'

export default function StatusBar() {
  const { gpu, device, activeModel, voicesCount } = useAppStore()

  return (
    <footer className="flex items-center justify-between h-7 px-4 bg-zinc-900 border-t border-zinc-700 text-xs text-zinc-500">
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1">
          {gpu?.available ? (
            <Zap className="w-3 h-3 text-green-500" />
          ) : (
            <Cpu className="w-3 h-3 text-yellow-500" />
          )}
          {device.toUpperCase()}
          {gpu?.name && ` - ${gpu.name}`}
        </span>

        {gpu?.available && gpu.vram_total_mb && (
          <span className="flex items-center gap-1">
            <HardDrive className="w-3 h-3" />
            VRAM: {gpu.vram_used_mb}MB / {gpu.vram_total_mb}MB
          </span>
        )}

        <span>
          Model: {activeModel || 'None loaded'}
        </span>
      </div>

      <div className="flex items-center gap-4">
        <span>Voices: {voicesCount}</span>
      </div>
    </footer>
  )
}
