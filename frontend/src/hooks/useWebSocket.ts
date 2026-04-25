import { useEffect, useRef, useState, useCallback } from 'react'

const MAX_RECONNECT_DELAY_MS = 30_000

export function useWebSocket(url: string, onMessage: (msg: string) => void, onEnd: () => void) {
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const onMessageRef = useRef(onMessage)
  const onEndRef = useRef(onEnd)
  const retryDelayRef = useRef(1000)
  const queueRef = useRef<string[]>([])  // messages sent while disconnected

  useEffect(() => { onMessageRef.current = onMessage }, [onMessage])
  useEffect(() => { onEndRef.current = onEnd }, [onEnd])

  useEffect(() => {
    let cancelled = false

    const connect = () => {
      if (cancelled) return
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (cancelled) return
        setIsConnected(true)
        retryDelayRef.current = 1000  // reset backoff on successful connect
        // Flush queued messages
        while (queueRef.current.length > 0) {
          ws.send(queueRef.current.shift()!)
        }
      }

      ws.onmessage = (e) => {
        if (e.data === '__END__') onEndRef.current()
        else onMessageRef.current(e.data)
      }

      ws.onclose = () => {
        setIsConnected(false)
        if (!cancelled) {
          // Exponential backoff capped at MAX_RECONNECT_DELAY_MS
          setTimeout(connect, retryDelayRef.current)
          retryDelayRef.current = Math.min(retryDelayRef.current * 2, MAX_RECONNECT_DELAY_MS)
        }
      }

      ws.onerror = () => ws.close()
    }

    connect()
    return () => {
      cancelled = true
      wsRef.current?.close()
    }
  }, [url])

  const send = useCallback((message: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(message)
    } else {
      // Queue message to send once reconnected (cap at 10 to prevent unbounded growth)
      if (queueRef.current.length < 10) {
        queueRef.current.push(message)
      }
    }
  }, [])

  return { isConnected, send }
}
