import { useEffect, useRef, useState } from 'react'

const BACKOFF_SCHEDULE_MS = [0, 1000, 2000, 4000, 8000, 16000, 30000]

/**
 * useWebSocket
 *
 * Manages a WebSocket connection to the given path with automatic reconnection
 * using exponential backoff (0 → 1s → 2s → 4s → max 30s).
 *
 * Returns:
 *   frameSrc   — object URL of the latest received frame (swap into <img> src)
 *   status     — 'connecting' | 'connected' | 'reconnecting' | 'disconnected'
 *   frameCount — monotonic count of frames received this session
 */
export default function useWebSocket(path) {
  const [frameSrc, setFrameSrc] = useState(null)
  const [status, setStatus] = useState('connecting')
  const [frameCount, setFrameCount] = useState(0)
  const wsRef = useRef(null)
  const attemptRef = useRef(0)
  const prevUrlRef = useRef(null)

  useEffect(() => {
    let cancelled = false

    function connect() {
      if (cancelled) return

      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const url = `${protocol}://${window.location.host}${path}`

      setStatus(attemptRef.current === 0 ? 'connecting' : 'reconnecting')

      const ws = new WebSocket(url)
      wsRef.current = ws
      ws.binaryType = 'blob'

      ws.onopen = () => {
        attemptRef.current = 0
        setStatus('connected')
      }

      ws.onmessage = (evt) => {
        // Pause rendering when tab is hidden — save CPU, keep connection alive
        if (document.hidden) return

        const blob = evt.data instanceof Blob ? evt.data : new Blob([evt.data])
        const newUrl = URL.createObjectURL(blob)

        setFrameSrc((prev) => {
          if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current)
          prevUrlRef.current = newUrl
          return newUrl
        })
        setFrameCount((n) => n + 1)
      }

      ws.onclose = () => {
        if (cancelled) return
        const delay = BACKOFF_SCHEDULE_MS[Math.min(attemptRef.current, BACKOFF_SCHEDULE_MS.length - 1)]
        attemptRef.current += 1
        setStatus('reconnecting')
        setTimeout(connect, delay)
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()

    return () => {
      cancelled = true
      if (wsRef.current) wsRef.current.close()
      if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current)
    }
  }, [path])

  return { frameSrc, status, frameCount }
}
