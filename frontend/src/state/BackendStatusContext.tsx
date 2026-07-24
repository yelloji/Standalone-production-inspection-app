import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react'

import { ApiClientError, inspectionApi } from '../api/client'
import type { ReadinessResponse } from '../api/contracts'
import { BackendStatusContext, type BackendStatus } from './backend-status'
const REFRESH_INTERVAL_MS = 15_000

export function BackendStatusProvider({
  children,
}: {
  readonly children: ReactNode
}) {
  const [refreshKey, setRefreshKey] = useState(0)
  const [state, setState] = useState<Omit<BackendStatus, 'refresh'>>({
    connection: 'checking',
    health: null,
    readiness: null,
    message: null,
    checkedAt: null,
  })

  const refresh = useCallback(() => setRefreshKey((value) => value + 1), [])

  useEffect(() => {
    const timer = window.setInterval(refresh, REFRESH_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [refresh])

  useEffect(() => {
    const controller = new AbortController()

    async function loadStatus() {
      try {
        const health = await inspectionApi.health(controller.signal)
        let readiness: ReadinessResponse | null = null
        let message: string | null = null
        try {
          readiness = await inspectionApi.readiness(controller.signal)
        } catch (error) {
          message = readableError(error)
        }
        setState({
          connection: 'connected',
          health,
          readiness,
          message,
          checkedAt: new Date(),
        })
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setState({
          connection: 'unavailable',
          health: null,
          readiness: null,
          message: readableError(error),
          checkedAt: new Date(),
        })
      }
    }

    void loadStatus()
    return () => controller.abort()
  }, [refreshKey])

  const value = useMemo(() => ({ ...state, refresh }), [refresh, state])
  return (
    <BackendStatusContext.Provider value={value}>
      {children}
    </BackendStatusContext.Provider>
  )
}

function readableError(error: unknown): string {
  if (error instanceof ApiClientError) {
    return error.message
  }
  return 'System status could not be checked.'
}
