import { useEffect } from 'react'
import { Cpu } from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import { apiFetch } from '../lib/api'

export default function Models() {
  const { models, fetchModels } = useAppStore()
  // Show all engines the backend registers (cloud mode has all, local has 3)
  const filteredModels = models

  useEffect(() => {
    fetchModels()
  }, [fetchModels])

  const handleLoad = async (name: string) => {
    try {
      await apiFetch(`/models/${name}/load`, { method: 'POST' })
      await fetchModels()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Load failed')
    }
  }

  const handleUnload = async (name: string) => {
    await apiFetch(`/models/${name}/unload`, { method: 'POST' })
    await fetchModels()
  }

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">AI Models</h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filteredModels.map((model) => (
          <div
            key={model.name}
            className="bg-zinc-900 border border-zinc-700 rounded-lg p-4"
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <h3 className="font-medium">{model.display_name}</h3>
                <p className="text-xs text-zinc-500 mt-1">{model.description}</p>
              </div>
              {model.is_loaded && (
                <span className="px-2 py-0.5 text-xs bg-green-500/10 text-green-400 rounded-full">
                  Active
                </span>
              )}
            </div>

            <div className="flex items-center gap-4 text-xs text-zinc-500 mb-3">
              <span>{model.languages.join(', ')}</span>
              <span>{model.model_size_mb}MB</span>
              <span>VRAM: {model.vram_required_mb}MB</span>
              <span className="text-zinc-600">{model.license}</span>
            </div>

            <div className="flex items-center gap-2">
              {!model.is_loaded && (
                <button
                  onClick={() => handleLoad(model.name)}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-md"
                >
                  <Cpu className="w-3 h-3" /> Load
                </button>
              )}
              {model.is_loaded && (
                <button
                  onClick={() => handleUnload(model.name)}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-md"
                >
                  Unload
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
