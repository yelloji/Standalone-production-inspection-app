import { useCallback, useEffect, useState } from 'react'

import { ApiClientError, inspectionApi } from '../api/client'
import type { ModelJobSummary, ModelSummary } from '../api/contracts'
import { Icon } from './Icon'
import { Button, StatusBadge, Surface } from './Primitives'

type Operation = 'import' | 'archive' | 'delete'

export function ModelLibrary({ hideHeading = false }: { readonly hideHeading?: boolean }) {
  const [models, setModels] = useState<readonly ModelSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [operation, setOperation] = useState<Operation | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadModels = useCallback(async (signal?: AbortSignal) => {
    try {
      const values = await inspectionApi.models(signal)
      setModels(values)
      setError(null)
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === 'AbortError') {
        return
      }
      setError(readableError(loadError))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()

    async function loadInitialModels() {
      try {
        const values = await inspectionApi.models(controller.signal)
        setModels(values)
        setError(null)
      } catch (loadError) {
        if (loadError instanceof DOMException && loadError.name === 'AbortError') {
          return
        }
        setError(readableError(loadError))
      } finally {
        setLoading(false)
      }
    }

    void loadInitialModels()
    return () => controller.abort()
  }, [])

  async function importBundle() {
    if (!window.productionInspection) {
      setError('Model import is available in the desktop application.')
      return
    }
    const sourcePath = await window.productionInspection.models.selectBundle()
    if (!sourcePath) {
      return
    }
    await runOperation(
      'import',
      () => inspectionApi.importModel(sourcePath),
      'Model bundle imported and validated.',
    )
  }

  async function archiveModel(model: ModelSummary) {
    if (
      !window.confirm(
        `Archive ${model.display_name} ${model.model_version}? It will remain stored for audit and can no longer be selected for new pipelines.`,
      )
    ) {
      return
    }
    await runOperation(
      'archive',
      () => inspectionApi.archiveModel(model.model_bundle_id),
      'Model archived. You may now permanently delete it if it has no dependencies.',
    )
  }

  async function deleteModel(model: ModelSummary) {
    if (
      !window.confirm(
        `Permanently delete ${model.display_name} ${model.model_version}? This removes its application-owned files and cannot be undone.`,
      )
    ) {
      return
    }
    await runOperation(
      'delete',
      () => inspectionApi.deleteModel(model.model_bundle_id),
      'Archived model permanently deleted.',
    )
  }

  async function runOperation(
    selectedOperation: Operation,
    submit: () => Promise<ModelJobSummary>,
    successMessage: string,
  ) {
    setOperation(selectedOperation)
    setError(null)
    setMessage(null)
    try {
      const submitted = await submit()
      const completed = await inspectionApi.waitForModelJob(submitted.job_id)
      if (completed.status === 'failed') {
        throw new ApiClientError(
          completed.message ?? 'The model operation did not complete.',
        )
      }
      setMessage(successMessage)
      await loadModels()
    } catch (operationError) {
      setError(readableError(operationError))
    } finally {
      setOperation(null)
    }
  }

  return (
    <Surface className="model-library">
      <div className="model-library__header">
        {hideHeading ? (
          <p>
            Import multiple model versions safely. Importing never changes the active
            production pipeline.
          </p>
        ) : (
          <div>
            <p className="eyebrow">Model library</p>
            <h2>Validated ONNX models</h2>
            <p>
              Import multiple model versions safely. Importing never changes the active
              production pipeline.
            </p>
          </div>
        )}
        <Button disabled={operation !== null} icon="layers" onClick={importBundle}>
          {operation === 'import' ? 'Validating bundle…' : 'Import model bundle'}
        </Button>
      </div>

      {message ? <div className="model-library__notice is-success">{message}</div> : null}
      {error ? (
        <div className="model-library__notice is-error" role="alert">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="model-library__empty">Loading model library…</div>
      ) : models.length === 0 ? (
        <div className="model-library__empty">
          <span className="empty-state__icon">
            <Icon name="layers" />
          </span>
          <strong>No models imported</strong>
          <span>Import a validated ONNX bundle to begin building a pipeline.</span>
        </div>
      ) : (
        <div className="model-list" aria-label="Imported models">
          {models.map((model) => (
            <article className="model-row" key={model.model_bundle_id}>
              <span className="model-row__icon">
                <Icon name="layers" />
              </span>
              <div className="model-row__identity">
                <strong>{model.display_name}</strong>
                <span>
                  Version {model.model_version} · {model.model_bundle_id}
                </span>
              </div>
              <StatusBadge
                label={stateLabel(model.state)}
                tone={stateTone(model.state)}
              />
              <div className="model-row__metadata">
                <small>Imported</small>
                <span>{new Date(model.created_at).toLocaleDateString()}</span>
              </div>
              <div className="model-row__actions">
                {model.can_archive ? (
                  <Button
                    disabled={operation !== null}
                    onClick={() => archiveModel(model)}
                    variant="secondary"
                  >
                    Archive
                  </Button>
                ) : null}
                {model.can_delete ? (
                  <Button
                    disabled={operation !== null}
                    onClick={() => deleteModel(model)}
                    variant="danger"
                  >
                    Delete
                  </Button>
                ) : null}
                {!model.can_archive && !model.can_delete ? (
                  <span className="model-row__protected">
                    {model.referenced_by_pipelines ? 'Used by pipeline' : 'Protected'}
                  </span>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      )}

      <div className="model-library__footer">
        <Icon name="shield" />
        <span>
          Active or referenced models cannot be removed. Permanent deletion requires
          archive first.
        </span>
      </div>
    </Surface>
  )
}

function readableError(error: unknown): string {
  return error instanceof ApiClientError
    ? error.message
    : 'The model operation could not be completed.'
}

function stateLabel(state: string): string {
  return state === 'retired'
    ? 'Archived'
    : state.charAt(0).toUpperCase() + state.slice(1)
}

function stateTone(
  state: string,
): 'positive' | 'warning' | 'danger' | 'neutral' | 'info' {
  if (state === 'active' || state === 'valid' || state === 'approved') {
    return 'positive'
  }
  if (state === 'rejected') {
    return 'danger'
  }
  if (state === 'retired') {
    return 'neutral'
  }
  return 'info'
}
