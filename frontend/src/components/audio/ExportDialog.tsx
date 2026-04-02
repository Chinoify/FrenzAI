import { useState } from 'react'
import { Download, X } from 'lucide-react'

interface ExportDialogProps {
  audioUrl: string
  onClose: () => void
}

export default function ExportDialog({ audioUrl, onClose }: ExportDialogProps) {
  const [format, setFormat] = useState('wav')

  const formats = [
    { value: 'wav', label: 'WAV', desc: '48kHz Lossless' },
    { value: 'mp3', label: 'MP3', desc: '320kbps' },
    { value: 'flac', label: 'FLAC', desc: 'Lossless compressed' },
  ]

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-zinc-800 border border-zinc-700 rounded-lg p-6 w-80">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-medium">Export Audio</h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-2 mb-4">
          {formats.map((f) => (
            <label
              key={f.value}
              className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer border ${
                format === f.value ? 'border-violet-500 bg-violet-500/10' : 'border-zinc-700'
              }`}
            >
              <input
                type="radio"
                name="format"
                value={f.value}
                checked={format === f.value}
                onChange={(e) => setFormat(e.target.value)}
                className="accent-violet-500"
              />
              <div>
                <div className="text-sm font-medium">{f.label}</div>
                <div className="text-xs text-zinc-500">{f.desc}</div>
              </div>
            </label>
          ))}
        </div>

        <a
          href={audioUrl}
          download={`frenzai_export.${format}`}
          className="flex items-center justify-center gap-2 w-full px-4 py-2 bg-violet-500 hover:bg-violet-600 rounded-lg text-sm font-medium"
          onClick={onClose}
        >
          <Download className="w-4 h-4" /> Export {format.toUpperCase()}
        </a>
      </div>
    </div>
  )
}
