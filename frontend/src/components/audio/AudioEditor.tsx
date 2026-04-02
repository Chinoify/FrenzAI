import { useEffect, useRef, useState, useCallback } from 'react'
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'
import TimelinePlugin from 'wavesurfer.js/dist/plugins/timeline.esm.js'
import {
  Play, Pause, Scissors, ZoomIn, ZoomOut, SkipBack, SkipForward,
  Loader2, Upload, Clock
} from 'lucide-react'
import { apiFetch, apiUpload, audioUrl as resolveAudioUrl } from '../../lib/api'

interface AudioEditorProps {
  /** Direct audio URL (for short files loaded in browser) */
  audioUrl?: string
  /** File object (for upload-first flow with long files) */
  file?: File
  onTrimmed?: (blob: Blob, start: number, end: number) => void
  height?: number
}

// Files under this size load directly in the browser; above = server-side processing
const BROWSER_LOAD_LIMIT_MB = 30

export default function AudioEditor({ audioUrl, file, onTrimmed, height = 140 }: AudioEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WaveSurfer | null>(null)
  const regionsRef = useRef<any>(null)

  const [playing, setPlaying] = useState(false)
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [zoom, setZoom] = useState(50)
  const [regionStart, setRegionStart] = useState(0)
  const [regionEnd, setRegionEnd] = useState(0)
  const [processing, setProcessing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadProgress, setLoadProgress] = useState(0)

  // For long files: server-side metadata
  const [longFileUrl, setLongFileUrl] = useState<string | null>(null)
  const [longFileDuration, setLongFileDuration] = useState(0)
  const [serverPeaks, setServerPeaks] = useState<number[] | null>(null)
  const [isLongFile, setIsLongFile] = useState(false)

  // Determine if file is "long" (> 50MB)
  useEffect(() => {
    if (file && file.size > BROWSER_LOAD_LIMIT_MB * 1024 * 1024) {
      setIsLongFile(true)
      uploadLongFile(file)
    } else {
      setIsLongFile(false)
    }
  }, [file])

  const uploadLongFile = async (f: File) => {
    setLoading(true)
    setLoadProgress(0)
    try {
      const form = new FormData()
      form.append('file', f)

      // Use XMLHttpRequest for upload progress on large files (up to 2GB)
      const result = await new Promise<{
        audio_url: string; duration: number; peaks: number[]; file_size_mb: number
      }>((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('POST', '/api/audio/upload-long')
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            const pct = Math.round((e.loaded / e.total) * 80) // Upload = 0-80%
            setLoadProgress(pct)
          }
        }
        xhr.onload = () => {
          if (xhr.status === 200) {
            setLoadProgress(90) // Processing = 80-100%
            resolve(JSON.parse(xhr.responseText))
          } else {
            reject(new Error(`Upload failed: ${xhr.statusText}`))
          }
        }
        xhr.onerror = () => reject(new Error('Upload failed — file may be too large'))
        xhr.send(form)
      })

      setLongFileUrl(result.audio_url)
      setLongFileDuration(result.duration)
      setServerPeaks(result.peaks)
      setDuration(result.duration)
      setRegionEnd(Math.min(30, result.duration))
      setLoadProgress(100)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  // Initialize wavesurfer for short files (direct browser load)
  const actualUrl = audioUrl || (file && !isLongFile ? URL.createObjectURL(file) : null)

  useEffect(() => {
    if (!containerRef.current || !actualUrl) return

    setLoading(true)
    const regions = RegionsPlugin.create()
    regionsRef.current = regions

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#6d28d9',
      progressColor: '#8b5cf6',
      cursorColor: '#a78bfa',
      barWidth: 2,
      barRadius: 2,
      barGap: 1,
      height,
      normalize: true,
      plugins: [
        regions,
        TimelinePlugin.create({
          timeInterval: 1,
          primaryLabelInterval: 5,
          style: { color: '#71717a', fontSize: '10px' },
        }),
      ],
    })

    ws.load(actualUrl)

    ws.on('loading', (pct: number) => setLoadProgress(pct))
    ws.on('ready', () => {
      const dur = ws.getDuration()
      setDuration(dur)
      setRegionEnd(dur)
      setLoading(false)
      regions.addRegion({
        start: 0,
        end: dur,
        color: 'rgba(139, 92, 246, 0.15)',
        drag: true,
        resize: true,
      })
    })

    ws.on('timeupdate', (time: number) => setCurrentTime(time))
    ws.on('play', () => setPlaying(true))
    ws.on('pause', () => setPlaying(false))
    regions.on('region-updated', (region: any) => {
      setRegionStart(region.start)
      setRegionEnd(region.end)
    })

    wsRef.current = ws
    return () => { ws.destroy() }
  }, [actualUrl, height])

  useEffect(() => { wsRef.current?.zoom(zoom) }, [zoom])

  const togglePlay = () => wsRef.current?.playPause()

  const playSelection = () => {
    const regions = regionsRef.current?.getRegions()
    if (regions?.length > 0) regions[0].play()
  }

  const seekBy = (seconds: number) => {
    if (wsRef.current) {
      const newTime = Math.max(0, Math.min(duration, currentTime + seconds))
      wsRef.current.seekTo(newTime / duration)
    } else if (isLongFile) {
      setCurrentTime(Math.max(0, Math.min(longFileDuration, currentTime + seconds)))
    }
  }

  const formatTime = (s: number) => {
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    const sec = Math.floor(s % 60)
    if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  const handleTrim = useCallback(async () => {
    if (!onTrimmed) return
    setProcessing(true)
    try {
      if (isLongFile && longFileUrl) {
        // Server-side extraction for long files
        const result = await apiFetch<{ audio_url: string }>('/audio/extract-segment', {
          method: 'POST',
          body: JSON.stringify({ audio_url: longFileUrl, start: regionStart, end: regionEnd }),
        })
        // Fetch the extracted segment as blob
        const resp = await fetch(resolveAudioUrl(result.audio_url))
        const blob = await resp.blob()
        onTrimmed(blob, regionStart, regionEnd)
      } else if (wsRef.current) {
        // Client-side trim for short files
        const audioBuffer = wsRef.current.getDecodedData()
        if (!audioBuffer) return
        const sr = audioBuffer.sampleRate
        const startSample = Math.floor(regionStart * sr)
        const endSample = Math.floor(regionEnd * sr)
        const length = endSample - startSample
        const offlineCtx = new OfflineAudioContext(1, length, sr)
        const newBuffer = offlineCtx.createBuffer(1, length, sr)
        const srcData = audioBuffer.getChannelData(0)
        const dstData = newBuffer.getChannelData(0)
        for (let i = 0; i < length; i++) dstData[i] = srcData[startSample + i]
        const wavBlob = audioBufferToWav(newBuffer)
        onTrimmed(wavBlob, regionStart, regionEnd)
      }
    } finally {
      setProcessing(false)
    }
  }, [regionStart, regionEnd, onTrimmed, isLongFile, longFileUrl])

  const selectionDuration = regionEnd - regionStart

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
      {/* Loading state */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-12 gap-3">
          <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
          <p className="text-sm text-zinc-400">
            {loadProgress < 80 ? 'Uploading audio...' : 'Processing waveform...'}
          </p>
          <div className="w-64 bg-zinc-800 rounded-full h-2">
            <div className="bg-violet-500 h-2 rounded-full transition-all" style={{ width: `${loadProgress}%` }} />
          </div>
          {file && (
            <p className="text-xs text-zinc-600">
              {(file.size / 1024 / 1024).toFixed(0)} MB
              {file.size > 500 * 1024 * 1024 && ' — large file, this may take a minute'}
              {file.size > 1024 * 1024 * 1024 && ' — very large file, please wait'}
            </p>
          )}
          <p className="text-[10px] text-zinc-600">{loadProgress}%</p>
        </div>
      )}

      {/* Waveform (short files) */}
      {!isLongFile && <div ref={containerRef} className={`px-2 pt-2 ${loading ? 'hidden' : ''}`} />}

      {/* Server-side peaks visualization (long files) */}
      {isLongFile && !loading && serverPeaks && (
        <div className="px-4 pt-4">
          <div className="flex items-end gap-[1px] h-24">
            {serverPeaks.map((peak, i) => {
              const isInRegion = (i / serverPeaks.length) * longFileDuration >= regionStart &&
                                 (i / serverPeaks.length) * longFileDuration <= regionEnd
              return (
                <div
                  key={i}
                  className={`flex-1 rounded-t transition-colors cursor-pointer ${
                    isInRegion ? 'bg-violet-500' : 'bg-zinc-700'
                  }`}
                  style={{ height: `${Math.max(2, peak * 100)}%` }}
                  onClick={() => {
                    const clickTime = (i / serverPeaks.length) * longFileDuration
                    setCurrentTime(clickTime)
                  }}
                />
              )
            })}
          </div>
          {/* Region selector for long files */}
          <div className="flex items-center gap-3 mt-3">
            <div className="flex-1">
              <label className="text-[10px] text-zinc-500">Start</label>
              <input
                type="range" min={0} max={longFileDuration} step={1} value={regionStart}
                onChange={(e) => setRegionStart(Math.min(Number(e.target.value), regionEnd - 5))}
                className="w-full"
              />
            </div>
            <div className="flex-1">
              <label className="text-[10px] text-zinc-500">End</label>
              <input
                type="range" min={0} max={longFileDuration} step={1} value={regionEnd}
                onChange={(e) => setRegionEnd(Math.max(Number(e.target.value), regionStart + 5))}
                className="w-full"
              />
            </div>
          </div>
        </div>
      )}

      {/* Time + Selection info */}
      {!loading && (
        <div className="flex items-center justify-between px-4 py-1.5 text-[10px] text-zinc-500 font-mono">
          <span>{formatTime(currentTime)}</span>
          <span className="flex items-center gap-1">
            <Clock className="w-2.5 h-2.5" />
            Selection: {formatTime(regionStart)} — {formatTime(regionEnd)} ({formatTime(selectionDuration)})
          </span>
          <span>{formatTime(duration || longFileDuration)}</span>
        </div>
      )}

      {/* Controls */}
      {!loading && (
        <div className="flex items-center gap-2 px-4 py-3 border-t border-zinc-800 flex-wrap">
          {/* Playback */}
          {!isLongFile && (
            <>
              <button onClick={togglePlay} className="w-9 h-9 flex items-center justify-center rounded-lg bg-violet-500 hover:bg-violet-600 transition-colors">
                {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
              </button>
              <button onClick={playSelection} className="px-3 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-xs text-zinc-400">
                Play Selection
              </button>
            </>
          )}

          {/* Navigation (both short and long) */}
          <div className="flex items-center gap-1">
            <button onClick={() => seekBy(-60)} className="p-1.5 bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-400 text-[10px]" title="-1min">
              <SkipBack className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => seekBy(-10)} className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 rounded text-[10px] text-zinc-400">-10s</button>
            <button onClick={() => seekBy(10)} className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 rounded text-[10px] text-zinc-400">+10s</button>
            <button onClick={() => seekBy(60)} className="p-1.5 bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-400" title="+1min">
              <SkipForward className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Zoom (short files only) */}
          {!isLongFile && (
            <div className="flex items-center gap-1">
              <button onClick={() => setZoom(Math.max(10, zoom - 20))} className="p-1.5 bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-400">
                <ZoomOut className="w-3.5 h-3.5" />
              </button>
              <input type="range" min={10} max={200} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} className="w-16" />
              <button onClick={() => setZoom(Math.min(200, zoom + 20))} className="p-1.5 bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-400">
                <ZoomIn className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <div className="flex-1" />

          {/* Selection quality indicator */}
          <span className={`text-[10px] px-2 py-1 rounded ${
            selectionDuration >= 10 && selectionDuration <= 30
              ? 'bg-emerald-500/10 text-emerald-400'
              : selectionDuration >= 5 && selectionDuration <= 60
              ? 'bg-amber-500/10 text-amber-400'
              : 'bg-red-500/10 text-red-400'
          }`}>
            {selectionDuration >= 10 && selectionDuration <= 30 ? 'Ideal length' :
             selectionDuration < 10 ? 'Too short' :
             selectionDuration <= 60 ? 'Acceptable' : 'Too long (trim more)'}
          </span>

          {/* Trim button */}
          {onTrimmed && (
            <button
              onClick={handleTrim}
              disabled={processing || selectionDuration < 3}
              className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 disabled:from-zinc-700 disabled:to-zinc-700 disabled:opacity-50 rounded-lg text-xs font-medium transition-all"
            >
              {processing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Scissors className="w-3.5 h-3.5" />}
              Trim to Selection
            </button>
          )}
        </div>
      )}
    </div>
  )
}


function audioBufferToWav(buffer: AudioBuffer): Blob {
  const sampleRate = buffer.sampleRate
  const samples = buffer.getChannelData(0)
  const dataLength = samples.length * 2
  const arrayBuffer = new ArrayBuffer(44 + dataLength)
  const view = new DataView(arrayBuffer)

  const writeStr = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
  }
  writeStr(0, 'RIFF')
  view.setUint32(4, 36 + dataLength, true)
  writeStr(8, 'WAVE')
  writeStr(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeStr(36, 'data')
  view.setUint32(40, dataLength, true)

  let offset = 44
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true)
    offset += 2
  }
  return new Blob([arrayBuffer], { type: 'audio/wav' })
}
