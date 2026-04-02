import { useEffect } from 'react'
import { useAppStore } from '../stores/appStore'

export function useModelStatus(pollIntervalMs = 5000) {
  const { fetchModels } = useAppStore()

  useEffect(() => {
    fetchModels()
    const interval = setInterval(fetchModels, pollIntervalMs)
    return () => clearInterval(interval)
  }, [fetchModels, pollIntervalMs])
}
