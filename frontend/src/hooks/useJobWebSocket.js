import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * WebSocket hook that connects to the job's real-time update channel.
 * Auto-reconnects with exponential backoff.
 */
export default function useJobWebSocket(jobId) {
  const [wsStatus, setWsStatus] = useState('connecting')
  const [latestAnalytics, setLatestAnalytics] = useState(null)
  const [progress, setProgress] = useState(0)
  const [isComplete, setIsComplete] = useState(false)
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)

  const wsRef = useRef(null)
  const reconnectAttemptRef = useRef(0)
  const reconnectTimerRef = useRef(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!jobId || !mountedRef.current) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/ws/jobs/${jobId}`

    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (!mountedRef.current) return
        setWsStatus('connected')
        setError(null)
        reconnectAttemptRef.current = 0
      }

      ws.onmessage = (event) => {
        if (!mountedRef.current) return
        try {
          const msg = JSON.parse(event.data)

          switch (msg.event) {
            case 'analytics':
              setLatestAnalytics(msg.data)
              if (msg.data?.progress_pct !== undefined) {
                setProgress(msg.data.progress_pct)
              }
              break
            case 'complete':
              setIsComplete(true)
              setSummary(msg.summary)
              setProgress(100)
              break
            case 'status':
              // Job status update
              break
            case 'connected':
              // Initial connection acknowledgment
              break
            case 'ping':
              // Keep-alive, ignore
              break
            case 'error':
              setError(msg.message || 'Processing error')
              break
            default:
              break
          }
        } catch (e) {
          console.warn('Failed to parse WebSocket message:', e)
        }
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        setWsStatus('disconnected')

        // Don't reconnect if job is complete
        if (isComplete) return

        // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
        const delay = Math.min(
          1000 * Math.pow(2, reconnectAttemptRef.current),
          30000
        )
        reconnectAttemptRef.current += 1

        reconnectTimerRef.current = setTimeout(() => {
          if (mountedRef.current) {
            setWsStatus('connecting')
            connect()
          }
        }, delay)
      }

      ws.onerror = () => {
        if (!mountedRef.current) return
        setWsStatus('error')
      }
    } catch (e) {
      setWsStatus('error')
      setError(e.message)
    }
  }, [jobId, isComplete])

  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [connect])

  return { wsStatus, latestAnalytics, progress, isComplete, summary, error }
}
