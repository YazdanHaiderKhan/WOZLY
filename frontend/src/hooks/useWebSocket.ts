import { useEffect, useRef, useCallback } from 'react'
import { useAuth } from './useAuth'
import { useCLS } from './useCLS'

type WSEvent = { type: 'roadmap_updated' | 'mastery_updated' | 'quiz_ready' | 'roadmap_progress'; payload: unknown }

type RoadmapProgressPayload = {
  stage: string
  progress: number
  message?: string
}

export function useWozlyWebSocket(options?: { onRoadmapProgress?: (payload: RoadmapProgressPayload) => void }) {
  const { user } = useAuth()
  const { invalidate } = useCLS()
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onRoadmapProgressRef = useRef(options?.onRoadmapProgress)

  useEffect(() => {
    onRoadmapProgressRef.current = options?.onRoadmapProgress
  }, [options?.onRoadmapProgress])

  const connect = useCallback(() => {
    if (!user) return
    const token = localStorage.getItem('access_token') ?? ''
    const WS_BASE = (import.meta as any).env.VITE_WS_BASE_URL || 'ws://localhost:8000'
    const url = `${WS_BASE}/ws/${user.user_id}?token=${token}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('[WS] Connected')
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }

    ws.onmessage = (e) => {
      try {
        const event: WSEvent = JSON.parse(e.data)
        if (event.type === 'roadmap_updated' || event.type === 'mastery_updated') {
          invalidate()
        }
        if (event.type === 'roadmap_progress' && onRoadmapProgressRef.current) {
          onRoadmapProgressRef.current(event.payload as RoadmapProgressPayload)
        }
      } catch { /* ignore */ }
    }

    ws.onclose = () => {
      // Auto-reconnect after 3 seconds
      reconnectTimer.current = setTimeout(connect, 3000)
    }

    ws.onerror = () => ws.close()
  }, [user, invalidate])

  useEffect(() => {
    connect()
    return () => {
      if (wsRef.current) wsRef.current.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }
  }, [connect])

  const ping = () => wsRef.current?.send(JSON.stringify({ type: 'ping' }))
  return { ping }
}
