import { useEffect, useRef, useState, useCallback } from 'react'

export function useWebSocket(url: string) {
  const [socket, setSocket] = useState<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const websocket = new WebSocket(url)
    
    websocket.onopen = () => {
      console.log('WS connected')
      setIsConnected(true)
    }
    
    websocket.onclose = () => {
      console.log('WS disconnected')
      setIsConnected(false)
    }

    websocket.onerror = (error) => {
      console.error('WS error:', error)
    }

    wsRef.current = websocket
    setSocket(websocket)

    return () => {
      websocket.close()
    }
  }, [url])

  const send = useCallback((message: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(message)
    } else {
      console.warn('WS not connected')
    }
  }, [])

  return { socket, isConnected, send }
}

