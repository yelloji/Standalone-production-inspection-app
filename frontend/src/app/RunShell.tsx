import { useEffect, useState } from 'react'
import { Link, Outlet } from 'react-router'

import { inspectionApi } from '../api/client'
import type { PipelineSummary } from '../api/contracts'
import { Icon } from '../components/Icon'
import { StatusBadge } from '../components/Primitives'
import { useBackendStatus } from '../state/backend-status'

export function RunShell() {
  const backend = useBackendStatus()
  const [activePipeline, setActivePipeline] = useState<PipelineSummary | null>(null)
  const backendStatus =
    backend.connection === 'checking'
      ? { label: 'Checking system', tone: 'info' as const }
      : backend.connection === 'connected'
        ? { label: 'System connected', tone: 'positive' as const }
        : { label: 'System unavailable', tone: 'danger' as const }

  useEffect(() => {
    if (backend.connection !== 'connected') {
      return
    }
    const controller = new AbortController()
    void inspectionApi
      .activePipeline(controller.signal)
      .then(setActivePipeline)
      .catch(() => setActivePipeline(null))
    return () => controller.abort()
  }, [backend.connection])

  return (
    <div className="run-shell">
      <header className="run-header">
        <Link className="run-brand" to="/run" aria-label="Production run home">
          <div className="brand__mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div>
            <strong>Inspection</strong>
            <span>Production station 01</span>
          </div>
        </Link>

        <div className="run-header__status">
          <span className="run-header__pipeline">
            <small>Active pipeline</small>
            <strong>
              {activePipeline
                ? `${activePipeline.display_name} · r${activePipeline.revision}`
                : 'Not configured'}
            </strong>
          </span>
          <StatusBadge label={backendStatus.label} tone={backendStatus.tone} />
          <Link className="mode-link" to="/configuration/pipelines">
            <Icon name="settings" />
            <span>Configuration</span>
          </Link>
        </div>
      </header>

      <main className="run-workspace">
        <Outlet context={{ activePipeline }} />
      </main>
    </div>
  )
}
