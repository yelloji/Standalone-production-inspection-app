import { useEffect, useRef, useState } from 'react'

import { inspectionApi } from '../api/client'
import type {
  CenterReferenceSummary,
  ReconstructionJobSummary,
} from '../api/contracts'
import { PageHeading, StatusBadge, Surface } from '../components/Primitives'

const RECONSTRUCTION_SESSION_KEY = 'inspection.reconstruction.session.v1'
type PreviewSize = 3000 | 4000 | 5000

interface SavedReconstructionSession {
  readonly jobId: string
  readonly sourcePath: string
  readonly side: 'upper' | 'lower'
  readonly previewSize: PreviewSize
}

export function ValidationPage() {
  const [initialSession] = useState(readSavedSession)
  const [sourcePath, setSourcePath] = useState(initialSession?.sourcePath ?? '')
  const [side, setSide] = useState<'upper' | 'lower'>(
    initialSession?.side ?? 'lower',
  )
  const [previewSize, setPreviewSize] = useState<PreviewSize>(
    initialSession?.previewSize ?? 5000,
  )
  const [job, setJob] = useState<ReconstructionJobSummary | null>(null)
  const [centerReferences, setCenterReferences] = useState<
    readonly CenterReferenceSummary[]
  >([])
  const [installingSide, setInstallingSide] = useState<
    'upper' | 'lower' | null
  >(null)
  const [error, setError] = useState<string | null>(null)
  const pollingController = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!initialSession) {
      return
    }
    const controller = new AbortController()
    pollingController.current = controller
    void monitorJob(initialSession.jobId, controller)
    return () => controller.abort()
  }, [initialSession])

  useEffect(() => {
    const controller = new AbortController()
    void loadCenterReferences(controller.signal)
    return () => controller.abort()
  }, [])

  async function loadCenterReferences(signal?: AbortSignal) {
    try {
      setCenterReferences(await inspectionApi.centerReferences(signal))
    } catch (reason) {
      if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
        setError(
          reason instanceof Error
            ? reason.message
            : 'Center reference status could not be loaded.',
        )
      }
    }
  }

  async function installCenterReference(selectedSide: 'upper' | 'lower') {
    setError(null)
    const bridge = window.productionInspection
    if (!bridge) {
      setError('Reference installation is available in the desktop application.')
      return
    }
    const selected = await bridge.centerReferences.selectImage(selectedSide)
    if (!selected) {
      return
    }
    setInstallingSide(selectedSide)
    try {
      await inspectionApi.importCenterReference(selected, selectedSide)
      await loadCenterReferences()
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'The approved center reference could not be installed.',
      )
    } finally {
      setInstallingSide(null)
    }
  }

  async function monitorJob(jobId: string, controller: AbortController) {
    try {
      const completed = await inspectionApi.waitForReconstructionJob(
        jobId,
        setJob,
        controller.signal,
      )
      if (completed.status === 'failed') {
        setError(completed.message ?? 'Reconstruction could not be completed.')
      }
    } catch (reason) {
      if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
        setError(
          reason instanceof Error
            ? reason.message
            : 'The reconstruction job could not be restored.',
        )
      }
    } finally {
      if (pollingController.current === controller) {
        pollingController.current = null
      }
    }
  }

  async function selectFolder() {
    setError(null)
    const bridge = window.productionInspection
    if (!bridge) {
      setError('Folder selection is available in the desktop application.')
      return
    }
    const selected = await bridge.acquisitions.selectFolder()
    if (selected) {
      setSourcePath(selected)
      setJob(null)
      clearSavedSession()
    }
  }

  async function reconstruct() {
    if (
      !sourcePath ||
      !centerReferences.some(
        (reference) => reference.side === side && reference.installed,
      ) ||
      job?.status === 'running' ||
      job?.status === 'queued'
    ) {
      return
    }
    setError(null)
    pollingController.current?.abort()
    const nextController = new AbortController()
    pollingController.current = nextController
    try {
      const submitted = await inspectionApi.submitReconstruction(
        sourcePath,
        side,
        previewSize,
      )
      setJob(submitted)
      saveSession({ jobId: submitted.job_id, sourcePath, side, previewSize })
      await monitorJob(submitted.job_id, nextController)
    } catch (reason) {
      if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
        setError(reason instanceof Error ? reason.message : 'Reconstruction failed.')
      }
    }
  }

  const busy = job?.status === 'queued' || job?.status === 'running'
  const selectedReference = centerReferences.find(
    (reference) => reference.side === side,
  )
  const centerReady = selectedReference?.installed === true
  const progress =
    job && job.progress_total > 0
      ? Math.round((job.progress_current / job.progress_total) * 100)
      : 0
  const previewUrl = job?.preview_url
    ? `http://127.0.0.1:8000${job.preview_url}`
    : null

  return (
    <div className="page">
      <PageHeading
        eyebrow="Offline validation"
        title="Reconstruct a complete brake disc"
        description="Select one ordered 16-image acquisition, verify every neighbor join, and create an uncropped full-cycle preview."
        action={
          <StatusBadge
            label={job?.production_approved ? 'Production gate passed' : 'Commissioning'}
            tone={job?.production_approved ? 'positive' : 'warning'}
          />
        }
      />
      {error ? <div className="form-message form-message--error">{error}</div> : null}
      <Surface className="reconstruction-workbench">
        <div className="reconstruction-controls">
          <div>
            <p className="eyebrow">Reconstruction demo</p>
            <h2>Ordered 16-frame acquisition</h2>
            <p className="muted-copy">
              Filenames must begin with positions 1 through 16. Position 1 is the
              acquisition start point; position 16 closes back to position 1.
            </p>
          </div>
          <div className="field-grid field-grid--compact">
            <label className="field">
              Disc side
              <select
                disabled={busy}
                value={side}
                onChange={(event) => setSide(event.target.value as 'upper' | 'lower')}
              >
                <option value="lower">Lower side</option>
                <option value="upper">Upper side</option>
              </select>
            </label>
            <label className="field">
              Saved image size
              <select
                disabled={busy}
                value={previewSize}
                onChange={(event) =>
                  setPreviewSize(Number(event.target.value) as PreviewSize)
                }
              >
                <option value={5000}>5000 × 5000</option>
                <option value={4000}>4000 × 4000</option>
                <option value={3000}>3000 × 3000</option>
              </select>
            </label>
          </div>
          <div className="folder-selection">
            <button className="secondary-button" disabled={busy} onClick={selectFolder}>
              Select 16-image folder
            </button>
            <span title={sourcePath}>{sourcePath || 'No acquisition selected'}</span>
          </div>
          <div className="center-reference-card">
            <div>
              <span>Approved {side} center</span>
              <strong>
                {centerReady
                  ? 'Ready for automatic completion'
                  : 'Reference installation required'}
              </strong>
            </div>
            <StatusBadge
              label={centerReady ? 'Ready' : 'Not installed'}
              tone={centerReady ? 'positive' : 'warning'}
            />
            {!centerReady ? (
              <button
                className="secondary-button"
                disabled={busy || installingSide !== null}
                onClick={() => installCenterReference(side)}
              >
                {installingSide === side
                  ? 'Installing reference…'
                  : `Install ${side} reference`}
              </button>
            ) : null}
          </div>
          <button
            className="primary-button"
            disabled={!sourcePath || !centerReady || busy}
            onClick={reconstruct}
          >
            {busy ? 'Reconstructing…' : 'Start reconstruction'}
          </button>
          {job ? (
            <div className="reconstruction-progress" aria-live="polite">
              <div>
                <strong>{stageLabel(job.stage)}</strong>
                <span>
                  {job.progress_current} / {job.progress_total}
                </span>
              </div>
              <progress max={100} value={progress} />
            </div>
          ) : null}
        </div>

        <div className="reconstruction-result">
          {previewUrl ? (
            <>
              <div className="reconstruction-result__header">
                <div>
                  <p className="eyebrow">Full-cycle result</p>
                  <h2>{job?.production_approved ? 'Validated reconstruction' : 'Review preview'}</h2>
                </div>
                <StatusBadge
                  label={
                    job?.production_approved
                      ? '≤ 1 px gate passed'
                      : 'Validation required'
                  }
                  tone={job?.production_approved ? 'positive' : 'warning'}
                />
              </div>
              <div className="reconstruction-preview">
                <img alt="Reconstructed full brake disc" src={previewUrl} />
              </div>
              <div className="reconstruction-metrics">
                <Metric label="Median error" value={pixels(job?.validation_median_px)} />
                <Metric label="95th percentile" value={pixels(job?.validation_p95_px)} />
                <Metric label="Maximum error" value={pixels(job?.validation_maximum_px)} />
                <Metric
                  label="Passing joins"
                  value={`${job?.passed_join_count ?? 0} / ${job?.total_join_count ?? 16}`}
                />
                <Metric
                  label="Center completion"
                  value={
                    job?.center_completion_applied
                      ? `${job.center_rotation_degrees?.toFixed(2) ?? '—'}°`
                      : '—'
                  }
                />
              </div>
              <p className="reconstruction-saved-path">
                Automatically saved as{' '}
                <strong>{job?.preview_relative_path ?? 'reconstructed-preview.png'}</strong>
                {job?.preview_width && job.preview_height
                  ? ` · ${job.preview_width} × ${job.preview_height} px`
                  : null}
              </p>
            </>
          ) : (
            <div className="reconstruction-empty">
              <span>16 × 22.5°</span>
              <h2>Full disc preview appears here</h2>
              <p>No crop is applied to the acquired frame rectangles.</p>
            </div>
          )}
        </div>
      </Surface>
    </div>
  )
}

function readSavedSession(): SavedReconstructionSession | null {
  try {
    const value = window.sessionStorage.getItem(RECONSTRUCTION_SESSION_KEY)
    if (!value) {
      return null
    }
    const parsed = JSON.parse(value) as Partial<SavedReconstructionSession>
    if (
      typeof parsed.jobId !== 'string' ||
      typeof parsed.sourcePath !== 'string' ||
      (parsed.side !== 'upper' && parsed.side !== 'lower') ||
      (parsed.previewSize !== undefined &&
        ![3000, 4000, 5000].includes(parsed.previewSize))
    ) {
      clearSavedSession()
      return null
    }
    return {
      jobId: parsed.jobId,
      sourcePath: parsed.sourcePath,
      side: parsed.side,
      previewSize: (parsed.previewSize as PreviewSize | undefined) ?? 5000,
    }
  } catch {
    clearSavedSession()
    return null
  }
}

function saveSession(value: SavedReconstructionSession): void {
  try {
    window.sessionStorage.setItem(RECONSTRUCTION_SESSION_KEY, JSON.stringify(value))
  } catch {
    // A blocked browser storage area must not stop reconstruction.
  }
}

function clearSavedSession(): void {
  try {
    window.sessionStorage.removeItem(RECONSTRUCTION_SESSION_KEY)
  } catch {
    // A blocked browser storage area must not stop reconstruction.
  }
}

function stageLabel(stage: string): string {
  return (
    {
      queued: 'Waiting to start',
      verifying: 'Verifying and copying 16 images',
      registering: 'Aligning neighboring frames',
      validating: 'Checking independent pixel evidence',
      rendering: 'Rendering full-cycle preview',
      completing_center: 'Completing approved center assembly',
      completed: 'Reconstruction complete',
      failed: 'Reconstruction stopped',
    }[stage] ?? stage
  )
}

function pixels(value: number | null | undefined): string {
  return value == null ? '—' : `${value.toFixed(2)} px`
}

function Metric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}
