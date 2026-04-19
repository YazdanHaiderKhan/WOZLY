import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { roadmapApi } from '../api/agents'
import { useAuth } from './useAuth'

// ─── localStorage helpers ──────────────────────────────────────────────────────

const lsKey = (uid: string) => `wozly_roadmap_${uid}`

function loadCache(uid: string): any | undefined {
  try {
    const raw = localStorage.getItem(lsKey(uid))
    return raw ? JSON.parse(raw) : undefined
  } catch {
    return undefined
  }
}

function saveCache(uid: string, data: any) {
  try {
    localStorage.setItem(lsKey(uid), JSON.stringify(data))
  } catch {
    // Storage quota exceeded — ignore silently
  }
}

/** Call this when the user clicks Reset Demo to wipe the local cache. */
export function clearRoadmapCache(uid: string) {
  try {
    localStorage.removeItem(lsKey(uid))
  } catch {}
}

// ─── Hook ──────────────────────────────────────────────────────────────────────

export function useCLS() {
  const { user } = useAuth()
  const qc = useQueryClient()

  // Read cached data synchronously before the query runs
  const cached = user?.user_id ? loadCache(user.user_id) : undefined

  const query = useQuery({
    queryKey: ['cls', user?.user_id],
    queryFn: async () => {
      const data = await roadmapApi.getRoadmap(user!.user_id)
      // Persist the fresh response — future reloads will be instant
      if (user?.user_id) saveCache(user.user_id, data)
      return data
    },
    enabled: !!user,
    // Provide cached data as the starting value — no loading spinner on reload
    initialData: cached,
    // Mark initialData as stale immediately → silent background refetch on mount
    initialDataUpdatedAt: 0,
    // Once freshly fetched, don't refetch again for 5 minutes
    staleTime: 5 * 60_000,
    gcTime: 10 * 60_000,
  })

  const invalidate = useCallback(() => {
    qc.invalidateQueries({ queryKey: ['cls', user?.user_id] })
  }, [qc, user?.user_id])

  return {
    roadmap: query.data?.roadmap ?? null,
    mastery: query.data?.mastery_snapshot ?? {},
    // Only show loading spinner if there's no cached data at all
    isLoading: query.isLoading && !cached,
    refetch: query.refetch,
    invalidate,
  }
}
