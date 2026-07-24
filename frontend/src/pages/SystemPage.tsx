import { Button, PageHeading, StatusBadge, Surface } from '../components/Primitives'
import { useBackendStatus } from '../state/backend-status'

const labels: Record<string, string> = {
  database: 'Database',
  run_commands: 'Run command worker',
  events: 'Event broker',
}

export function SystemPage() {
  const backend = useBackendStatus()
  const connected = backend.connection === 'connected'

  return (
    <div className="page">
      <PageHeading
        eyebrow="Diagnostics"
        title="System status"
        description="A clear view of local application health and production service readiness."
        action={
          <Button icon="refresh" onClick={backend.refresh} variant="secondary">
            Refresh status
          </Button>
        }
      />
      <div className="status-summary">
        <Surface className="status-summary__hero">
          <StatusBadge
            label={connected ? 'Application connected' : 'Connection unavailable'}
            tone={connected ? 'positive' : 'danger'}
          />
          <h2>
            {connected
              ? 'Desktop services are responding'
              : 'Backend connection needs attention'}
          </h2>
          <p>
            {backend.message ??
              'Core health is available. Individual production services are listed below.'}
          </p>
          <dl>
            <div>
              <dt>Service</dt>
              <dd>{backend.health?.service ?? '—'}</dd>
            </div>
            <div>
              <dt>Version</dt>
              <dd>{backend.health?.version ?? '—'}</dd>
            </div>
            <div>
              <dt>Last checked</dt>
              <dd>
                {backend.checkedAt?.toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                }) ?? 'Checking…'}
              </dd>
            </div>
          </dl>
        </Surface>
        <Surface className="component-status">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Local services</p>
              <h2>Component health</h2>
            </div>
          </div>
          <div className="component-status__list">
            {Object.entries(labels).map(([key, label]) => {
              const ready = backend.readiness?.components[key] === 'ready'
              return (
                <div key={key}>
                  <span>
                    <strong>{label}</strong>
                    <small>
                      {ready ? 'Operating normally' : 'Not configured or unavailable'}
                    </small>
                  </span>
                  <StatusBadge
                    label={ready ? 'Ready' : 'Not ready'}
                    tone={ready ? 'positive' : 'warning'}
                  />
                </div>
              )
            })}
          </div>
        </Surface>
      </div>
    </div>
  )
}
