import { ModelLibrary } from '../components/ModelLibrary'
import { PageHeading, StatusBadge } from '../components/Primitives'

export function ModelLibraryPage() {
  return (
    <div className="page">
      <PageHeading
        eyebrow="Model library"
        title="Validated ONNX models"
        description="Import and manage model versions independently. A model is selected only when AI inference is enabled in a pipeline."
        action={<StatusBadge label="Application controlled" tone="info" />}
      />
      <ModelLibrary hideHeading />
    </div>
  )
}
