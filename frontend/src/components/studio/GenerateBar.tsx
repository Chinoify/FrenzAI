import { Sparkles, Loader2 } from 'lucide-react'
import { useStudioStore } from '../../stores/studioStore'

export default function GenerateBar() {
  const { text, generating, progress, generate, selectedModel } = useStudioStore()

  return (
    <div className="flex items-center justify-between px-4 py-3 bg-zinc-800 rounded-lg border border-zinc-700">
      <button
        onClick={generate}
        disabled={generating || !text.trim()}
        className="flex items-center gap-2 px-6 py-2.5 bg-violet-500 hover:bg-violet-600 disabled:bg-zinc-700 disabled:text-zinc-500 rounded-lg text-sm font-medium transition-colors"
      >
        {generating ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Generating...
          </>
        ) : (
          <>
            <Sparkles className="w-4 h-4" />
            Generate Speech
          </>
        )}
      </button>

      <div className="flex items-center gap-4 text-xs text-zinc-500">
        {progress && <span>{progress}</span>}
        <span>Cost: Free</span>
        <span className="text-zinc-600">|</span>
        <span>{selectedModel}</span>
      </div>
    </div>
  )
}
