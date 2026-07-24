import { Link } from 'react-router'

import { Icon } from '../components/Icon'
import { Button, PageHeading, StatusBadge, Surface } from '../components/Primitives'
import { useBackendStatus } from '../state/backend-status'

export function ProductionPage() {
  const backend = useBackendStatus()
  const coreReady = backend.readiness?.status === 'ready'

  return (
    <div className="page page--production">
      <PageHeading
        eyebrow="Run mode"
        title="Production inspection"
        description="Start inspection and follow each completed acquisition cycle from one clear workspace."
        action={
          <StatusBadge
            label={coreReady ? 'Core services ready' : 'Setup required'}
            tone={coreReady ? 'positive' : 'warning'}
          />
        }
      />

      <div className="operator-grid">
        <Surface className="run-card">
          <div className="run-card__visual" aria-hidden="true">
            <div className="disc-visual">
              <span className="disc-visual__hub" />
              <span className="disc-visual__orbit disc-visual__orbit--one" />
              <span className="disc-visual__orbit disc-visual__orbit--two" />
              <span className="disc-visual__sweep" />
            </div>
          </div>
          <div className="run-card__content">
            <p className="eyebrow">Current state</p>
            <h2>
              {coreReady ? 'Pipeline approval required' : 'System setup required'}
            </h2>
            <p>
              {coreReady
                ? 'A technician must validate and activate the inspection pipeline before production can start.'
                : 'The inspection station is waiting for technical configuration.'}
            </p>
            <Button disabled>Start production run</Button>
            <small>Start unlocks only when the station is ready for production.</small>
          </div>
        </Surface>

        <Surface className="latest-cycle">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Latest cycle</p>
              <h2>Waiting for inspection</h2>
            </div>
            <span className="cycle-state">
              <span aria-hidden="true" />
              No result
            </span>
          </div>

          <div className="cycle-placeholder" aria-hidden="true">
            <Icon name="disc" />
            <span />
          </div>

          <dl className="cycle-facts">
            <div>
              <dt>Acquisition</dt>
              <dd>16 images</dd>
            </div>
            <div>
              <dt>Disc side</dt>
              <dd>—</dd>
            </div>
            <div>
              <dt>Result</dt>
              <dd>—</dd>
            </div>
          </dl>

          <Link className="previous-inspections-link" to="/run/history">
            <Icon name="archive" />
            Previous inspections
            <Icon name="chevron" />
          </Link>
        </Surface>
      </div>

      <div className={`operator-message ${coreReady ? '' : 'operator-message--warning'}`}>
        <span className="operator-message__icon" aria-hidden="true">
          {coreReady ? '✓' : '!'}
        </span>
        <div>
          <strong>
            {coreReady ? 'Core system is available' : 'Configuration is required'}
          </strong>
          <span>
            {coreReady
              ? 'Production remains locked until an approved pipeline is active.'
              : 'Please ask a technician to complete station setup.'}
          </span>
        </div>
      </div>
    </div>
  )
}
