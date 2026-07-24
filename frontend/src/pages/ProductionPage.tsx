import { Link, useOutletContext } from 'react-router'

import type { PipelineSummary } from '../api/contracts'
import { Icon } from '../components/Icon'
import { Button, PageHeading, StatusBadge, Surface } from '../components/Primitives'
import { useBackendStatus } from '../state/backend-status'

export function ProductionPage() {
  const backend = useBackendStatus()
  const { activePipeline } = useOutletContext<{
    readonly activePipeline: PipelineSummary | null
  }>()
  const productionReady =
    backend.connection === 'connected' && activePipeline !== null

  return (
    <div className="page page--production">
      <PageHeading
        eyebrow="Run mode"
        title="Production inspection"
        description="Start inspection and follow each completed acquisition cycle from one clear workspace."
        action={
          <StatusBadge
            label={productionReady ? 'Pipeline active' : 'Setup required'}
            tone={productionReady ? 'positive' : 'warning'}
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
              {productionReady && activePipeline.acquisition_mode === 'automatic_folder'
                ? 'Ready to monitor acquisitions'
                : productionReady
                  ? 'Ready for production'
                  : 'System setup required'}
            </h2>
            <p>
              {productionReady
                ? activePipeline.acquisition_mode === 'automatic_folder'
                  ? `Waiting for ${activePipeline.expected_frame_count} images matching ${activePipeline.filename_template}.`
                  : `${activePipeline.display_name} revision ${activePipeline.revision} is approved and active.`
                : 'The inspection station is waiting for an approved active pipeline.'}
            </p>
            <Button disabled>Start production run</Button>
            <small>Run execution will be connected in the Production Run task.</small>
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

      {productionReady && activePipeline.acquisition_mode === 'automatic_folder' ? (
        <Surface className="intake-status">
          <div className="intake-status__heading">
            <div>
              <p className="eyebrow">Automatic acquisition intake</p>
              <h2>Waiting for acquisition</h2>
            </div>
            <StatusBadge label={`0 / ${activePipeline.expected_frame_count} received`} />
          </div>
          <div className="intake-progress" aria-label="Automatic intake workflow">
            <span className="is-current">Waiting</span>
            <span>Receiving images</span>
            <span>Verifying files</span>
            <span>Validating order</span>
            <span>Processing</span>
          </div>
          <p>
            Images are detected and ordered automatically. Production never guesses from
            timestamps and never processes a partially written cycle.
          </p>
        </Surface>
      ) : null}

      <div
        className={`operator-message ${
          productionReady ? '' : 'operator-message--warning'
        }`}
      >
        <span className="operator-message__icon" aria-hidden="true">
          {productionReady ? '✓' : '!'}
        </span>
        <div>
          <strong>
            {productionReady
              ? 'Production pipeline is active'
              : 'Configuration is required'}
          </strong>
          <span>
            {productionReady
              ? 'Run Mode loaded the exact approved pipeline snapshot.'
              : 'Please ask a technician to validate and activate a pipeline.'}
          </span>
        </div>
      </div>
    </div>
  )
}
