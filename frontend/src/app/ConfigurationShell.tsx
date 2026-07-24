import { Link, NavLink, Outlet } from 'react-router'

import { Icon, type IconName } from '../components/Icon'
import { StatusBadge } from '../components/Primitives'
import { useBackendStatus } from '../state/backend-status'

const configurationNavigation: ReadonlyArray<{
  readonly to: string
  readonly label: string
  readonly description: string
  readonly icon: IconName
}> = [
  {
    to: '/configuration/pipelines',
    label: 'Pipeline Builder',
    description: 'Stages and versions',
    icon: 'settings',
  },
  {
    to: '/configuration/models',
    label: 'Model Library',
    description: 'Validated ONNX models',
    icon: 'layers',
  },
  {
    to: '/configuration/validation',
    label: 'Offline Validation',
    description: 'Test before activation',
    icon: 'shield',
  },
  {
    to: '/configuration/system',
    label: 'System Status',
    description: 'Health and diagnostics',
    icon: 'activity',
  },
]

export function ConfigurationShell() {
  const backend = useBackendStatus()
  const connected = backend.connection === 'connected'

  return (
    <div className="app-shell app-shell--configuration">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand__mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div>
            <strong>Configuration</strong>
            <span>Technical workspace</span>
          </div>
        </div>

        <nav className="primary-nav" aria-label="Configuration navigation">
          <p className="primary-nav__label">Commissioning</p>
          {configurationNavigation.map((item) => (
            <NavLink
              className={({ isActive }) =>
                `primary-nav__item${isActive ? ' primary-nav__item--active' : ''}`
              }
              key={item.to}
              to={item.to}
            >
              <Icon name={item.icon} />
              <span>
                <strong>{item.label}</strong>
                <small>{item.description}</small>
              </span>
              <Icon className="primary-nav__chevron" name="chevron" />
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__footer">
          <div className="sidebar__station">
            <span className="sidebar__station-icon">
              <Icon name="shield" />
            </span>
            <span>
              <small>Protected mode</small>
              <strong>Technical access</strong>
            </span>
          </div>
          <p>Standalone runtime · v0.1.0</p>
        </div>
      </aside>

      <div className="app-frame">
        <header className="topbar">
          <div className="topbar__identity">
            <span>Configuration mode</span>
            <strong>Brake disc inspection</strong>
          </div>
          <div className="topbar__status">
            <StatusBadge
              label={connected ? 'Backend connected' : 'Backend unavailable'}
              tone={connected ? 'positive' : 'danger'}
            />
            <Link className="return-run-link" to="/run">
              <Icon name="disc" />
              Return to Run Mode
            </Link>
          </div>
        </header>

        <main className="workspace">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
