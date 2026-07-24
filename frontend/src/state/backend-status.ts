import { createContext, useContext } from 'react'

import type { HealthResponse, ReadinessResponse } from '../api/contracts'

export type ConnectionState = 'checking' | 'connected' | 'unavailable'

export interface BackendStatus {
  readonly connection: ConnectionState
  readonly health: HealthResponse | null
  readonly readiness: ReadinessResponse | null
  readonly message: string | null
  readonly checkedAt: Date | null
  readonly refresh: () => void
}

export const BackendStatusContext = createContext<BackendStatus | null>(null)

export function useBackendStatus(): BackendStatus {
  const value = useContext(BackendStatusContext)
  if (!value) {
    throw new Error('useBackendStatus must be used inside BackendStatusProvider')
  }
  return value
}
