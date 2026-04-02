import { Clipboard, Trash2 } from 'lucide-react'
import { useStudioStore } from '../../stores/studioStore'
import { MAX_TEXT_LENGTH } from '../../lib/constants'

export default function TextEditor() {
  const { text, setText, generating } = useStudioStore()

  const paragraphs = text.split(/\n\n+/).filter((p) => p.trim())
  const charCount = text.length

  const handlePaste = async () => {
    try {
      const clip = await navigator.clipboard.readText()
      setText(text + clip)
    } catch {
      // clipboard not available
    }
  }

  const handleClear = () => {
    if (text.length > 50 && !confirm('Clear all text?')) return
    setText('')
  }

  return (
    <div className="flex flex-col bg-zinc-800 rounded-lg border border-zinc-700">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value.slice(0, MAX_TEXT_LENGTH))}
        placeholder="Type or paste your text here..."
        disabled={generating}
        className="flex-1 min-h-[200px] p-4 bg-transparent text-zinc-100 text-sm resize-none focus:outline-none placeholder-zinc-600"
        onKeyDown={(e) => {
          if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault()
            useStudioStore.getState().generate()
          }
        }}
      />
      <div className="flex items-center justify-between px-4 py-2 border-t border-zinc-700 text-xs text-zinc-500">
        <div className="flex items-center gap-3">
          <span className={charCount > MAX_TEXT_LENGTH * 0.9 ? 'text-yellow-500' : ''}>
            {charCount.toLocaleString()} / {MAX_TEXT_LENGTH.toLocaleString()}
          </span>
          {paragraphs.length > 1 && (
            <span className="text-zinc-600">{paragraphs.length} paragraphs detected</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleClear}
            disabled={!text}
            className="flex items-center gap-1 px-2 py-1 rounded hover:bg-zinc-700 disabled:opacity-30"
          >
            <Trash2 className="w-3 h-3" /> Clear
          </button>
          <button
            onClick={handlePaste}
            className="flex items-center gap-1 px-2 py-1 rounded hover:bg-zinc-700"
          >
            <Clipboard className="w-3 h-3" /> Paste
          </button>
        </div>
      </div>
    </div>
  )
}
