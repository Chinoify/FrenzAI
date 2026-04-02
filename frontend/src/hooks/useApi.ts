import { useState, useCallback } from 'react'
import { apiFetch } from '../lib/api'

export function useApi<T>() {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const request = useCallback(async (path: string, options?: RequestInit) => {
    setLoading(true)
    setError(null)
    try {
      const result = await apiFetch<T>(path, options)
      setData(result)
      return result
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Request failed'
      setError(msg)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  return { data, loading, error, request }
}
