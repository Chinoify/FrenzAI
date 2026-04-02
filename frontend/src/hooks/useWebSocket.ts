import { useState, useRef, useCallback, useEffect } from 'react'

export function useWebSocket(url: string) {
  const [connected, setConnected] = useState(false)
  const ws = useRef<WebSocket | null>(null)
  const onMessage = useRef<((data: unknown) => void) | null>(null)

  const connect = useCallback(() => {
    ws.current = new WebSocket(url)
    ws.current.onopen = () => setConnected(true)
    ws.current.onclose = () => setConnected(false)
    ws.current.onmessage = (e) => {
      const data = JSON.parse(e.data)
      onMessage.current?.(data)
    }
  }, [url])

  const disconnect = useCallback(() => {
    ws.current?.close()
    setConnected(false)
  }, [])

  const send = useCallback((data: unknown) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }, [])

  const setOnMessage = useCallback((handler: (data: unknown) => void) => {
    onMessage.current = handler
  }, [])

  useEffect(() => {
    return () => { ws.current?.close() }
  }, [])

  return { connected, connect, disconnect, send, setOnMessage }
}
