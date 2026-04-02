import { useState, useEffect, useRef } from 'react'
import {
  Settings as SettingsIcon, Monitor, Volume2,
  Cpu, Keyboard, Eye, Code, Upload, Download, RotateCcw, Check
} from 'lucide-react'
import { useSettingsStore } from '../stores/settingsStore'
import { useAppStore } from '../stores/appStore'
import { apiFetch } from '../lib/api'

type Category = 'general' | 'audio' | 'gpu' | 'shortcuts' | 'accessibility' | 'developer'

const CATEGORIES: { id: Category; label: string; icon: typeof SettingsIcon }[] = [
  { id: 'general', label: 'General', icon: Monitor },
  { id: 'audio', label: 'Audio Engine', icon: Volume2 },
  { id: 'gpu', label: 'GPU & Performance', icon: Cpu },
  { id: 'shortcuts', label: 'Shortcuts', icon: Keyboard },
  { id: 'accessibility', label: 'Display', icon: Eye },
  { id: 'developer', label: 'Developer', icon: Code },
]

function Slider({ label, value, onChange, min, max, step = 1, unit = '', warning = '' }: {
  label: string; value: number; onChange: (v: number) => void; min: number; max: number; step?: number; unit?: string; warning?: string
}) {
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-zinc-400">{label}</span>
        <span className="text-zinc-300">{value}{unit}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 bg-zinc-700 rounded-full appearance-none cursor-pointer accent-violet-500" />
      {warning && <p className="text-[10px] text-amber-400 mt-1">{warning}</p>}
    </div>
  )
}

function Toggle({ label, checked, onChange, desc = '' }: { label: string; checked: boolean; onChange: (v: boolean) => void; desc?: string }) {
  return (
    <div className="flex items-center justify-between py-1">
      <div>
        <span className="text-sm text-zinc-300">{label}</span>
        {desc && <p className="text-[10px] text-zinc-500">{desc}</p>}
      </div>
      <button onClick={() => onChange(!checked)}
        className={`w-9 h-5 rounded-full transition-colors relative ${checked ? 'bg-violet-500' : 'bg-zinc-600'}`}>
        <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${checked ? 'left-[18px]' : 'left-0.5'}`} />
      </button>
    </div>
  )
}

function SelectSetting({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-sm text-zinc-300">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="px-2 py-1 bg-zinc-800 border border-zinc-700 rounded text-xs text-zinc-300">
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  )
}

function SectionHeader({ title }: { title: string }) {
  return <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mt-4 mb-2 first:mt-0">{title}</h3>
}

export default function Settings() {
  const [activeCategory, setActiveCategory] = useState<Category>('general')
  const [search, setSearch] = useState('')
  const [saved, setSaved] = useState(false)
  const [diagnostics, setDiagnostics] = useState<any>(null)
  const { settings, updateSetting, resetAll, exportSettings, importSettings, loadFromServer } = useSettingsStore()
  const { gpu, device, version, models } = useAppStore()
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { loadFromServer() }, [loadFromServer])

  const set = (key: string, value: unknown) => {
    updateSetting(key, value)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleExport = () => {
    const blob = new Blob([exportSettings()], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'frenzai-settings.json'
    a.click()
  }

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        importSettings(ev.target?.result as string)
        setSaved(true)
        setTimeout(() => setSaved(false), 2000)
      } catch { alert('Invalid settings file') }
    }
    reader.readAsText(file)
  }

  const runDiagnostics = async () => {
    try {
      const data = await apiFetch<any>('/system/diagnostics')
      setDiagnostics(data)
    } catch { alert('Failed to run diagnostics') }
  }

  const renderCategory = () => {
    switch (activeCategory) {
      case 'general': return (
        <div className="space-y-3">
          <SectionHeader title="Application" />
          <SelectSetting label="Theme" value={settings.theme} onChange={(v) => set('theme', v)}
            options={[{ value: 'dark', label: 'Dark' }, { value: 'light', label: 'Light' }, { value: 'system', label: 'System' }]} />
          <SelectSetting label="Font Size" value={settings.font_size} onChange={(v) => set('font_size', v)}
            options={[{ value: 'small', label: 'Small' }, { value: 'medium', label: 'Medium' }, { value: 'large', label: 'Large' }]} />
          <Toggle label="Compact Mode" checked={settings.compact_mode} onChange={(v) => set('compact_mode', v)} desc="Reduce padding for more content" />
          <SelectSetting label="Auto-save Interval" value={String(settings.auto_save_interval)} onChange={(v) => set('auto_save_interval', Number(v))}
            options={[{ value: '30', label: '30 seconds' }, { value: '60', label: '1 minute' }, { value: '300', label: '5 minutes' }, { value: '0', label: 'Manual only' }]} />
          <SelectSetting label="Startup Page" value={settings.startup_page} onChange={(v) => set('startup_page', v)}
            options={[{ value: '/', label: 'Studio' }, { value: '/projects', label: 'Audiobooks' }, { value: '/history', label: 'History' }]} />
          <SectionHeader title="Notifications" />
          <Toggle label="Generation Complete" checked={settings.notification_generation_complete} onChange={(v) => set('notification_generation_complete', v)} />
          <Toggle label="Error Alerts" checked={settings.notification_errors} onChange={(v) => set('notification_errors', v)} />
          <Toggle label="Sound on Complete" checked={settings.notification_sound} onChange={(v) => set('notification_sound', v)} />
          {settings.notification_sound && (
            <Slider label="Notification Volume" value={settings.notification_volume} onChange={(v) => set('notification_volume', v)} min={0} max={100} unit="%" />
          )}
          <SectionHeader title="System Info" />
          <div className="space-y-1.5 text-xs text-zinc-400">
            <div className="flex justify-between"><span>Version</span><span className="text-zinc-300">{version || '1.0.0'}</span></div>
            <div className="flex justify-between"><span>Device</span><span className="text-zinc-300">{device.toUpperCase()}</span></div>
            <div className="flex justify-between"><span>GPU</span><span className="text-zinc-300">{gpu?.name || 'N/A'}</span></div>
            {gpu?.vram_total_mb && <div className="flex justify-between"><span>VRAM</span><span className="text-zinc-300">{gpu.vram_total_mb}MB</span></div>}
          </div>
        </div>
      )

      case 'audio': return (
        <div className="space-y-3">
          <SectionHeader title="TTS Model" />
          <SelectSetting label="Active TTS Model" value={settings.active_tts_model} onChange={(v) => set('active_tts_model', v)}
            options={models.map((m) => ({ value: m.name, label: `${m.display_name} (${m.vram_required_mb}MB)` }))} />
          <SelectSetting label="Generation Quality" value={settings.generation_quality} onChange={(v) => set('generation_quality', v)}
            options={[{ value: 'draft', label: 'Draft (Fastest)' }, { value: 'standard', label: 'Standard' }, { value: 'high', label: 'High' }, { value: 'ultra', label: 'Ultra' }]} />
          <Slider label="Temperature" value={settings.default_temperature} onChange={(v) => set('default_temperature', v)} min={0.1} max={1.0} step={0.05} />
          <Toggle label="Random Seed" checked={settings.random_seed} onChange={(v) => set('random_seed', v)} desc="Same text produces different audio each time" />
          <Slider label="Max Tokens per Chunk" value={settings.max_tokens_per_chunk} onChange={(v) => set('max_tokens_per_chunk', v)} min={100} max={500} />
          <Slider label="Batch Size" value={settings.batch_size} onChange={(v) => set('batch_size', v)} min={1} max={8}
            warning={settings.batch_size > 4 ? 'May cause VRAM overflow on 4GB GPU' : ''} />
          <SelectSetting label="Fallback Model" value={settings.fallback_model} onChange={(v) => set('fallback_model', v)}
            options={[{ value: 'builtin', label: 'Built-in (Windows)' }, ...models.filter((m) => m.name !== settings.active_tts_model).map((m) => ({ value: m.name, label: m.display_name }))]} />
          <SectionHeader title="STT (Whisper)" />
          <SelectSetting label="Whisper Model" value={settings.active_stt_model} onChange={(v) => set('active_stt_model', v)}
            options={[{ value: 'tiny', label: 'Tiny (fastest)' }, { value: 'base', label: 'Base (balanced)' }, { value: 'small', label: 'Small' }, { value: 'medium', label: 'Medium' }, { value: 'large-v3', label: 'Large v3 (best)' }]} />
          <SelectSetting label="Default Language" value={settings.stt_language} onChange={(v) => set('stt_language', v)}
            options={[{ value: 'auto', label: 'Auto-detect' }, { value: 'en', label: 'English' }, { value: 'es', label: 'Spanish' }, { value: 'fr', label: 'French' }, { value: 'de', label: 'German' }, { value: 'ja', label: 'Japanese' }, { value: 'zh', label: 'Chinese' }]} />
          <Toggle label="Word Timestamps" checked={settings.stt_word_timestamps} onChange={(v) => set('stt_word_timestamps', v)} desc="Required for .srt export" />
          <Toggle label="VAD Filter" checked={settings.stt_vad_filter} onChange={(v) => set('stt_vad_filter', v)} desc="Skip silence segments" />
          <Slider label="Beam Size" value={settings.stt_beam_size} onChange={(v) => set('stt_beam_size', v)} min={1} max={10} />
        </div>
      )

      case 'gpu': return (
        <div className="space-y-3">
          <SectionHeader title="GPU Configuration" />
          <div className="bg-zinc-800 rounded-lg p-3 space-y-2">
            <div className="flex justify-between text-xs"><span className="text-zinc-400">GPU</span><span className="text-zinc-300">{gpu?.name || 'N/A'}</span></div>
            <div className="flex justify-between text-xs"><span className="text-zinc-400">VRAM Total</span><span className="text-zinc-300">{gpu?.vram_total_mb || 0} MB</span></div>
            <div className="flex justify-between text-xs"><span className="text-zinc-400">VRAM Used</span><span className="text-zinc-300">{gpu?.vram_used_mb || 0} MB</span></div>
            <div className="flex justify-between text-xs"><span className="text-zinc-400">VRAM Free</span><span className="text-green-400">{gpu?.vram_free_mb || 0} MB</span></div>
            {gpu?.vram_total_mb && (
              <div className="w-full bg-zinc-700 rounded-full h-2 mt-1">
                <div className="bg-violet-500 h-2 rounded-full" style={{ width: `${((gpu.vram_used_mb || 0) / gpu.vram_total_mb) * 100}%` }} />
              </div>
            )}
          </div>
          <Slider label="VRAM Warning Threshold" value={settings.vram_warn_threshold} onChange={(v) => set('vram_warn_threshold', v)} min={70} max={95} unit="%" />
          <Slider label="VRAM Critical Threshold" value={settings.vram_critical_threshold} onChange={(v) => set('vram_critical_threshold', v)} min={80} max={99} unit="%" />
          <Toggle label="Auto-flush on Critical" checked={settings.auto_flush_vram} onChange={(v) => set('auto_flush_vram', v)} />
          <SelectSetting label="Compute Precision" value={settings.compute_precision} onChange={(v) => set('compute_precision', v)}
            options={[{ value: 'float32', label: 'FP32 (most accurate)' }, { value: 'float16', label: 'FP16 (recommended)' }, { value: 'int8', label: 'INT8 (smallest)' }]} />
          <Toggle label="Force CPU Mode" checked={settings.force_cpu} onChange={(v) => set('force_cpu', v)} desc="Use CPU instead of GPU" />
          <SectionHeader title="Performance" />
          <Slider label="Parallel Threads" value={settings.parallel_threads} onChange={(v) => set('parallel_threads', v)} min={1} max={8}
            warning={settings.parallel_threads > 4 ? 'May cause VRAM overflow on 4GB GPU' : ''} />
          <Toggle label="Show VRAM in Header" checked={settings.show_vram_in_header} onChange={(v) => set('show_vram_in_header', v)} />
          <Toggle label="Show CPU in Header" checked={settings.show_cpu_in_header} onChange={(v) => set('show_cpu_in_header', v)} />
        </div>
      )

      case 'shortcuts': return (
        <div className="space-y-3">
          <SectionHeader title="Keyboard Shortcuts" />
          <div className="space-y-1">
            {[
              ['Ctrl + Enter', 'Generate speech'],
              ['Ctrl + Space', 'Play/pause audio'],
              ['Ctrl + S', 'Save current project'],
              ['Ctrl + D', 'Download last audio'],
              ['Ctrl + Shift + C', 'Copy transcript'],
              ['Ctrl + K', 'Command palette'],
              ['Ctrl + N', 'New project'],
              ['Escape', 'Close modal / cancel'],
              ['F5', 'Re-generate last'],
            ].map(([key, action]) => (
              <div key={key} className="flex items-center justify-between py-1.5 border-b border-zinc-800">
                <span className="text-sm text-zinc-300">{action}</span>
                <kbd className="px-2 py-0.5 bg-zinc-800 border border-zinc-700 rounded text-[10px] text-zinc-400 font-mono">{key}</kbd>
              </div>
            ))}
          </div>
        </div>
      )

      case 'accessibility': return (
        <div className="space-y-3">
          <SectionHeader title="Display" />
          <Toggle label="Reduce Motion" checked={settings.reduce_motion} onChange={(v) => set('reduce_motion', v)} desc="Disable animations" />
          <Toggle label="High Contrast" checked={settings.high_contrast} onChange={(v) => set('high_contrast', v)} />
          <Slider label="Text Scaling" value={settings.text_scaling} onChange={(v) => set('text_scaling', v)} min={80} max={140} unit="%" />
          <SelectSetting label="Waveform Style" value={settings.waveform_style} onChange={(v) => set('waveform_style', v)}
            options={[{ value: 'bars', label: 'Bars' }, { value: 'line', label: 'Line' }, { value: 'mirror', label: 'Mirror' }, { value: 'filled', label: 'Filled' }]} />
          <SelectSetting label="Accent Color" value={settings.color_theme} onChange={(v) => set('color_theme', v)}
            options={[{ value: 'purple', label: 'Purple' }, { value: 'blue', label: 'Blue' }, { value: 'green', label: 'Green' }, { value: 'amber', label: 'Amber' }, { value: 'red', label: 'Red' }]} />
        </div>
      )

      case 'developer': return (
        <div className="space-y-3">
          <SectionHeader title="Debug" />
          <Toggle label="Developer Mode" checked={settings.developer_mode} onChange={(v) => set('developer_mode', v)} desc="Show extra debug info" />
          <SelectSetting label="Log Level" value={settings.log_level} onChange={(v) => set('log_level', v)}
            options={[{ value: 'ERROR', label: 'Error' }, { value: 'WARN', label: 'Warning' }, { value: 'INFO', label: 'Info' }, { value: 'DEBUG', label: 'Debug' }]} />
          <SectionHeader title="Diagnostics" />
          <button onClick={runDiagnostics}
            className="w-full px-3 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-xs text-zinc-300 transition-colors">
            Run Diagnostics
          </button>
          {diagnostics && (
            <div className="bg-zinc-800 rounded-lg p-3 space-y-1 text-xs">
              <div className="flex justify-between"><span>Python</span><span className={diagnostics.python_version ? 'text-green-400' : 'text-red-400'}>{diagnostics.python_version || 'Missing'}</span></div>
              <div className="flex justify-between"><span>FFmpeg</span><span className={diagnostics.ffmpeg_installed ? 'text-green-400' : 'text-red-400'}>{diagnostics.ffmpeg_installed ? 'Installed' : 'Missing'}</span></div>
              <div className="flex justify-between"><span>CUDA</span><span className={diagnostics.cuda_available ? 'text-green-400' : 'text-red-400'}>{diagnostics.cuda_available ? 'Available' : 'Not available'}</span></div>
              <div className="flex justify-between"><span>GPU</span><span className="text-zinc-300">{diagnostics.gpu_name || 'N/A'}</span></div>
              <div className="flex justify-between"><span>Disk Free</span><span className="text-zinc-300">{diagnostics.disk_free_gb?.toFixed(1)} GB</span></div>
              {diagnostics.models?.map((m: any) => (
                <div key={m.name} className="flex justify-between">
                  <span>{m.name}</span>
                  <span className={m.loaded ? 'text-green-400' : 'text-zinc-500'}>{m.loaded ? 'Loaded' : 'Available'}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )

      default: return null
    }
  }

  return (
    <div className="flex gap-8">
      {/* Left — Category tabs */}
      <div className="w-48 flex-shrink-0 space-y-1">
        {CATEGORIES.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setActiveCategory(id)}
            className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm transition-all ${
              activeCategory === id ? 'bg-violet-500/10 text-violet-400' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/50'
            }`}>
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Right — Settings panel */}
      <div className="flex-1 max-w-xl">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold">
            {CATEGORIES.find((c) => c.id === activeCategory)?.label}
          </h2>
            <div className="flex items-center gap-2">
              {saved && <span className="flex items-center gap-1 text-xs text-green-400"><Check className="w-3 h-3" /> Saved</span>}
              <button onClick={handleExport} className="flex items-center gap-1 px-2 py-1 bg-zinc-800 hover:bg-zinc-700 rounded text-[10px] text-zinc-400">
                <Download className="w-3 h-3" /> Export
              </button>
              <button onClick={() => fileInputRef.current?.click()} className="flex items-center gap-1 px-2 py-1 bg-zinc-800 hover:bg-zinc-700 rounded text-[10px] text-zinc-400">
                <Upload className="w-3 h-3" /> Import
              </button>
              <input ref={fileInputRef} type="file" accept=".json" onChange={handleImport} className="hidden" />
              <button onClick={() => { if (confirm('Reset all settings to defaults?')) resetAll() }}
                className="flex items-center gap-1 px-2 py-1 bg-zinc-800 hover:bg-red-500/20 hover:text-red-400 rounded text-[10px] text-zinc-400">
                <RotateCcw className="w-3 h-3" /> Reset
              </button>
            </div>
          </div>
        {renderCategory()}
      </div>
    </div>
  )
}
