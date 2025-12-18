import { useEffect, useRef, useState, useCallback } from 'react'

interface WebSocketMessage {
  type: string
  task_id?: string
  timestamp?: string
  [key: string]: unknown
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

export function useWebSocket(taskId: string | null, options: UseWebSocketOptions = {}) {
  const {
    onMessage,
    reconnectInterval = 5000,
    maxReconnectAttempts = 3,
  } = options

  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
  const onMessageRef = useRef(onMessage)

  // Keep onMessage ref updated
  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = undefined
    }
    if (wsRef.current) {
      wsRef.current.onclose = null // Prevent reconnect on intentional close
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  useEffect(() => {
    if (!taskId) return

    const connect = () => {
      // Connect directly to backend, bypassing Vite proxy for WebSocket
      const wsUrl = `ws://localhost:8000/ws/${taskId}`

      try {
        const ws = new WebSocket(wsUrl)

        ws.onopen = () => {
          console.log(`[WS] Connected to ${taskId}`)
          setIsConnected(true)
          reconnectAttemptsRef.current = 0
        }

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data) as WebSocketMessage
            setLastMessage(message)
            onMessageRef.current?.(message)
          } catch (e) {
            console.error('[WS] Failed to parse message:', e)
          }
        }

        ws.onclose = (event) => {
          console.log(`[WS] Disconnected (code: ${event.code})`)
          setIsConnected(false)
          wsRef.current = null

          // Only reconnect if not intentionally closed and under max attempts
          if (event.code !== 1000 && reconnectAttemptsRef.current < maxReconnectAttempts) {
            reconnectAttemptsRef.current++
            console.log(`[WS] Reconnecting... (attempt ${reconnectAttemptsRef.current})`)
            reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval)
          }
        }

        ws.onerror = (error) => {
          console.error('[WS] Error:', error)
        }

        wsRef.current = ws
      } catch (e) {
        console.error('[WS] Failed to create WebSocket:', e)
      }
    }

    connect()

    return () => {
      disconnect()
    }
  }, [taskId, reconnectInterval, maxReconnectAttempts, disconnect])

  const sendMessage = useCallback((message: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  return {
    isConnected,
    lastMessage,
    sendMessage,
    disconnect,
  }
}
