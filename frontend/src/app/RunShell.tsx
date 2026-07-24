import { Link, Outlet } from 'react-router'

import { Icon } from '../components/Icon'
import { StatusBadge } from '../components/Primitives'
import { useBackendStatus } from '../state/backend-status'

export function RunShell() {
  const backend = useBackendStatus()
  const backendStatus =
    backend.connection === 'checking'
      ? { label: 'Checking system', tone: 'info' as const }
      : backend.connection === 'connected'
        ? { label: 'System connected', tone: 'positive' as const }
        : { label: 'System unavailable', tone: 'danger' as const }

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
            <strong>Not configured</strong>
          </span>
          <StatusBadge label={backendStatus.label} tone={backendStatus.tone} />
          <Link className="mode-link" to="/configuration/setup">
            <Icon name="settings" />
            <span>Configuration</span>
          </Link>
        </div>
      </header>

      <main className="run-workspace">
        <Outlet />
      </main>
    </div>
  )
}
