import {
  type FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'

import { inspectionApi } from '../api/client'
import type {
  DiscSide,
  InferenceMode,
  ModelSummary,
  PipelineDraftRequest,
  PipelineSummary,
} from '../api/contracts'
import { Button, PageHeading, StatusBadge, Surface } from '../components/Primitives'

const initialForm = {
  pipelineId: 'brake-disc-inspection',
  displayName: 'Brake Disc Inspection',
  side: 'upper' as DiscSide,
  expectedFrames: 16,
  automaticIntake: true,
  filenameTemplate: '{cycle}_{position}.jpg',
  positionWidth: 2,
  stableForMilliseconds: 1500,
  cycleTimeoutSeconds: 120,
  reconstructionEnabled: true,
  segmentCount: 16,
  inferenceEnabled: true,
  modelBundleId: '',
  inferenceMode: 'sahi' as InferenceMode,
  confidenceThreshold: 0.4,
  overlapRatio: 0.5,
  batchSize: 32,
}

export function PipelinePage() {
  const [form, setForm] = useState(initialForm)
  const [models, setModels] = useState<readonly ModelSummary[]>([])
  const [pipelines, setPipelines] = useState<readonly PipelineSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [nextModels, nextPipelines] = await Promise.all([
        inspectionApi.models(),
        inspectionApi.pipelines(),
      ])
      setModels(nextModels)
      setPipelines(nextPipelines)
      if (!form.modelBundleId) {
        const available = nextModels.find((model) =>
          ['valid', 'approved', 'active'].includes(model.state),
        )
        if (available) {
          setForm((current) => ({
            ...current,
            modelBundleId: current.modelBundleId || available.model_bundle_id,
          }))
        }
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Pipeline data is unavailable.')
    } finally {
      setLoading(false)
    }
  }, [form.modelBundleId])

  useEffect(() => {
    const controller = new AbortController()
    async function loadInitial() {
      try {
        const [nextModels, nextPipelines] = await Promise.all([
          inspectionApi.models(controller.signal),
          inspectionApi.pipelines(controller.signal),
        ])
        setModels(nextModels)
        setPipelines(nextPipelines)
        const available = nextModels.find((model) =>
          ['valid', 'approved', 'active'].includes(model.state),
        )
        if (available) {
          setForm((current) => ({
            ...current,
            modelBundleId: current.modelBundleId || available.model_bundle_id,
          }))
        }
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === 'AbortError') {
          return
        }
        setError(
          reason instanceof Error ? reason.message : 'Pipeline data is unavailable.',
        )
      } finally {
        setLoading(false)
      }
    }
    void loadInitial()
    return () => controller.abort()
  }, [])

  const validModels = useMemo(
    () =>
      models.filter((model) =>
        ['valid', 'approved', 'active'].includes(model.state),
      ),
    [models],
  )

  const saveDraft = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setMessage(null)
    setError(null)
    if (!form.reconstructionEnabled && !form.inferenceEnabled) {
      setError('Enable reconstruction, AI inference, or both.')
      return
    }
    if (form.inferenceEnabled && !form.modelBundleId) {
      setError('Select a validated model when AI inference is enabled.')
      return
    }

    setBusyId('create')
    try {
      const request: PipelineDraftRequest = {
        pipeline_id: form.pipelineId,
        display_name: form.displayName,
        model_bundle_id: form.inferenceEnabled ? form.modelBundleId : null,
        acquisition: {
          source: form.automaticIntake ? 'online' : 'offline',
          expected_frame_count: form.expectedFrames,
          ordered: true,
          side: form.side,
          mode: form.automaticIntake ? 'automatic_folder' : 'manual_folder',
          automatic: form.automaticIntake
            ? {
                filename_template: form.filenameTemplate,
                position_width: form.positionWidth,
                stable_for_milliseconds: form.stableForMilliseconds,
                incomplete_cycle_timeout_seconds: form.cycleTimeoutSeconds,
              }
            : null,
        },
        reconstruction: form.reconstructionEnabled
          ? {
              enabled: true,
              segment_count: form.segmentCount,
              degrees_per_segment: 360 / form.segmentCount,
            }
          : {
              enabled: false,
              segment_count: null,
              degrees_per_segment: null,
            },
        inference: form.inferenceEnabled
          ? {
              enabled: true,
              mode: form.inferenceMode,
              confidence_threshold: form.confidenceThreshold,
              sahi:
                form.inferenceMode === 'sahi'
                  ? {
                      slice_width: 1312,
                      slice_height: 1312,
                      overlap_width_ratio: form.overlapRatio,
                      overlap_height_ratio: form.overlapRatio,
                      batch_size: form.batchSize,
                    }
                  : null,
            }
          : {
              enabled: false,
              mode: null,
              confidence_threshold: null,
              sahi: null,
            },
      }
      const created = await inspectionApi.createPipeline(request)
      setMessage(`${created.display_name} revision ${created.revision} saved as a draft.`)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The draft could not be saved.')
    } finally {
      setBusyId(null)
    }
  }

  const validate = async (pipeline: PipelineSummary) => {
    setBusyId(pipeline.pipeline_snapshot_id)
    setMessage(null)
    setError(null)
    try {
      const validated = await inspectionApi.validatePipeline(
        pipeline.pipeline_snapshot_id,
      )
      setMessage(
        `${validated.display_name} revision ${validated.revision} passed configuration validation.`,
      )
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Validation failed.')
    } finally {
      setBusyId(null)
    }
  }

  const activate = async (pipeline: PipelineSummary) => {
    if (
      !window.confirm(
        `Approve and activate ${pipeline.display_name} revision ${pipeline.revision} for Run Mode?`,
      )
    ) {
      return
    }
    setBusyId(pipeline.pipeline_snapshot_id)
    setMessage(null)
    setError(null)
    try {
      const active = await inspectionApi.activatePipeline(
        pipeline.pipeline_snapshot_id,
      )
      setMessage(
        `${active.display_name} revision ${active.revision} is now active in Run Mode.`,
      )
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Activation failed.')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="page">
      <PageHeading
        eyebrow="Pipeline builder"
        title="Production pipeline"
        description="Choose only the stages this product needs, save a version, validate it, and deliberately activate it for operators."
        action={<StatusBadge label="Version controlled" tone="info" />}
      />

      {error ? <div className="form-message form-message--error">{error}</div> : null}
      {message ? <div className="form-message form-message--success">{message}</div> : null}

      <form className="pipeline-builder" onSubmit={(event) => void saveDraft(event)}>
        <Surface className="pipeline-identity">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Identity and input</p>
              <h2>Name this production recipe</h2>
            </div>
          </div>
          <div className="field-grid">
            <label className="field">
              <span>Pipeline name</span>
              <input
                maxLength={500}
                required
                value={form.displayName}
                onChange={(event) =>
                  setForm({ ...form, displayName: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Stable identifier</span>
              <input
                pattern="[A-Za-z0-9][A-Za-z0-9._-]*"
                required
                value={form.pipelineId}
                onChange={(event) =>
                  setForm({ ...form, pipelineId: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Disc side</span>
              <select
                value={form.side}
                onChange={(event) =>
                  setForm({ ...form, side: event.target.value as DiscSide })
                }
              >
                <option value="upper">Upper side</option>
                <option value="lower">Lower side</option>
                <option value="not_applicable">Not side-specific</option>
              </select>
            </label>
            <label className="field">
              <span>Images per cycle</span>
              <input
                max={100000}
                min={1}
                required
                type="number"
                value={form.expectedFrames}
                onChange={(event) =>
                  setForm({ ...form, expectedFrames: Number(event.target.value) })
                }
              />
            </label>
          </div>
          <div className="acquisition-mode">
            <label className="stage-card__toggle">
              <span>
                <strong>Automatic acquisition intake</strong>
                <small>
                  Run Mode watches the station source and orders each cycle from its
                  configured filenames.
                </small>
              </span>
              <input
                checked={form.automaticIntake}
                type="checkbox"
                onChange={(event) =>
                  setForm({ ...form, automaticIntake: event.target.checked })
                }
              />
            </label>
            {form.automaticIntake ? (
              <div className="automatic-intake-fields">
                <label className="field automatic-intake-fields__template">
                  <span>Filename template</span>
                  <input
                    required
                    value={form.filenameTemplate}
                    onChange={(event) =>
                      setForm({ ...form, filenameTemplate: event.target.value })
                    }
                  />
                  <small>
                    Required tokens: {'{cycle}'} and {'{position}'}. Example:{' '}
                    {form.filenameTemplate
                      .replace('{cycle}', 'DISC-0001')
                      .replace(
                        '{position}',
                        String(1).padStart(form.positionWidth, '0'),
                      )}
                  </small>
                </label>
                <label className="field">
                  <span>Position digits</span>
                  <input
                    max={6}
                    min={1}
                    type="number"
                    value={form.positionWidth}
                    onChange={(event) =>
                      setForm({ ...form, positionWidth: Number(event.target.value) })
                    }
                  />
                </label>
                <label className="field">
                  <span>File stable for</span>
                  <select
                    value={form.stableForMilliseconds}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        stableForMilliseconds: Number(event.target.value),
                      })
                    }
                  >
                    <option value={500}>0.5 seconds</option>
                    <option value={1000}>1 second</option>
                    <option value={1500}>1.5 seconds</option>
                    <option value={2000}>2 seconds</option>
                    <option value={3000}>3 seconds</option>
                  </select>
                </label>
                <label className="field">
                  <span>Incomplete timeout</span>
                  <input
                    max={86400}
                    min={1}
                    type="number"
                    value={form.cycleTimeoutSeconds}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        cycleTimeoutSeconds: Number(event.target.value),
                      })
                    }
                  />
                  <small>Seconds before an incomplete cycle is reported.</small>
                </label>
              </div>
            ) : (
              <p className="muted-copy">
                Manual offline validation will require a technician to select an ordered
                image set.
              </p>
            )}
          </div>
        </Surface>

        <div className="stage-grid">
          <StageCard
            checked={form.reconstructionEnabled}
            description="Combine the ordered acquisition into a complete disc image."
            title="Reconstruction"
            onChange={(checked) =>
              setForm({ ...form, reconstructionEnabled: checked })
            }
          >
            <label className="field">
              <span>Segments per cycle</span>
              <input
                disabled={!form.reconstructionEnabled}
                max={100000}
                min={1}
                type="number"
                value={form.segmentCount}
                onChange={(event) =>
                  setForm({ ...form, segmentCount: Number(event.target.value) })
                }
              />
              <small>{360 / form.segmentCount}° per image</small>
            </label>
          </StageCard>

          <StageCard
            checked={form.inferenceEnabled}
            description="Run the selected validated ONNX model on the acquired images."
            title="AI inference"
            onChange={(checked) => setForm({ ...form, inferenceEnabled: checked })}
          >
            <label className="field">
              <span>Validated model</span>
              <select
                disabled={!form.inferenceEnabled}
                required={form.inferenceEnabled}
                value={form.modelBundleId}
                onChange={(event) =>
                  setForm({ ...form, modelBundleId: event.target.value })
                }
              >
                <option value="">Select a model</option>
                {validModels.map((model) => (
                  <option key={model.model_bundle_id} value={model.model_bundle_id}>
                    {model.display_name} · {model.model_version}
                  </option>
                ))}
              </select>
              {form.inferenceEnabled && validModels.length === 0 ? (
                <small>Import a validated model from Model Library first.</small>
              ) : null}
            </label>
            <div className="field-grid field-grid--compact">
              <label className="field">
                <span>Inference method</span>
                <select
                  disabled={!form.inferenceEnabled}
                  value={form.inferenceMode}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      inferenceMode: event.target.value as InferenceMode,
                    })
                  }
                >
                  <option value="sahi">SAHI sliced</option>
                  <option value="direct">Normal/direct</option>
                </select>
              </label>
              <label className="field">
                <span>Confidence</span>
                <input
                  disabled={!form.inferenceEnabled}
                  max={1}
                  min={0}
                  step={0.01}
                  type="number"
                  value={form.confidenceThreshold}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      confidenceThreshold: Number(event.target.value),
                    })
                  }
                />
              </label>
            </div>
            {form.inferenceMode === 'sahi' ? (
              <div className="field-grid field-grid--compact">
                <label className="field">
                  <span>Overlap</span>
                  <input
                    disabled={!form.inferenceEnabled}
                    max={1}
                    min={0}
                    step={0.05}
                    type="number"
                    value={form.overlapRatio}
                    onChange={(event) =>
                      setForm({ ...form, overlapRatio: Number(event.target.value) })
                    }
                  />
                </label>
                <label className="field">
                  <span>Batch size</span>
                  <input
                    disabled={!form.inferenceEnabled}
                    max={1024}
                    min={1}
                    type="number"
                    value={form.batchSize}
                    onChange={(event) =>
                      setForm({ ...form, batchSize: Number(event.target.value) })
                    }
                  />
                </label>
              </div>
            ) : null}
          </StageCard>
        </div>

        <div className="pipeline-save-bar">
          <div>
            <strong>Save as a new immutable revision</strong>
            <span>Active production settings are never edited in place.</span>
          </div>
          <Button disabled={busyId !== null} type="submit">
            {busyId === 'create' ? 'Saving…' : 'Save draft'}
          </Button>
        </div>
      </form>

      <Surface className="pipeline-versions">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Saved versions</p>
            <h2>Validation and activation</h2>
          </div>
          <StatusBadge
            label={`${pipelines.length} version${pipelines.length === 1 ? '' : 's'}`}
          />
        </div>
        {loading ? <p className="muted-copy">Loading saved pipelines…</p> : null}
        {!loading && pipelines.length === 0 ? (
          <div className="pipeline-empty">
            <strong>No pipeline versions yet</strong>
            <span>Configure the required stages and save the first draft.</span>
          </div>
        ) : null}
        <div className="pipeline-list">
          {pipelines.map((pipeline) => (
            <article className="pipeline-row" key={pipeline.pipeline_snapshot_id}>
              <div className="pipeline-row__identity">
                <strong>{pipeline.display_name}</strong>
                <span>
                  Revision {pipeline.revision} · {pipeline.pipeline_id}
                </span>
              </div>
              <div className="pipeline-row__stages">
                <span
                  className={
                    pipeline.acquisition_mode === 'automatic_folder'
                      ? 'is-enabled'
                      : ''
                  }
                >
                  {pipeline.acquisition_mode === 'automatic_folder'
                    ? 'Automatic intake'
                    : 'Manual intake'}
                </span>
                <span className={pipeline.reconstruction_enabled ? 'is-enabled' : ''}>
                  Reconstruction
                </span>
                <span className={pipeline.inference_enabled ? 'is-enabled' : ''}>
                  AI inference
                </span>
              </div>
              <StatusBadge
                label={pipeline.state}
                tone={
                  pipeline.state === 'active'
                    ? 'positive'
                    : pipeline.state === 'validated' ||
                        pipeline.state === 'approved'
                      ? 'info'
                      : 'neutral'
                }
              />
              <div className="pipeline-row__actions">
                {pipeline.can_validate ? (
                  <Button
                    disabled={busyId !== null}
                    type="button"
                    variant="secondary"
                    onClick={() => void validate(pipeline)}
                  >
                    Validate
                  </Button>
                ) : null}
                {pipeline.can_activate ? (
                  <Button
                    disabled={busyId !== null}
                    type="button"
                    onClick={() => void activate(pipeline)}
                  >
                    Approve & activate
                  </Button>
                ) : null}
                {pipeline.state === 'active' ? (
                  <strong className="pipeline-row__active">Used by Run Mode</strong>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </Surface>
    </div>
  )
}

function StageCard({
  title,
  description,
  checked,
  onChange,
  children,
}: {
  readonly title: string
  readonly description: string
  readonly checked: boolean
  readonly onChange: (checked: boolean) => void
  readonly children: ReactNode
}) {
  return (
    <Surface className={`stage-card${checked ? ' stage-card--enabled' : ''}`}>
      <label className="stage-card__toggle">
        <span>
          <strong>{title}</strong>
          <small>{description}</small>
        </span>
        <input
          checked={checked}
          type="checkbox"
          onChange={(event) => onChange(event.target.checked)}
        />
      </label>
      <div className="stage-card__settings">{children}</div>
    </Surface>
  )
}
