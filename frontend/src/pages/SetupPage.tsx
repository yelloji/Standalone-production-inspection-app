import { Icon } from '../components/Icon'
import { PageHeading, StatusBadge, Surface } from '../components/Primitives'

const setupAreas = [
  {
    title: 'Model bundle',
    description: 'Import and verify a protected ONNX model package.',
    icon: 'layers' as const,
    step: '01',
  },
  {
    title: 'Inspection pipeline',
    description: 'Create a versioned configuration without changing production.',
    icon: 'settings' as const,
    step: '02',
  },
  {
    title: 'Offline validation',
    description: 'Prove accuracy and performance before approval.',
    icon: 'shield' as const,
    step: '03',
  },
]

export function SetupPage() {
  return (
    <div className="page">
      <PageHeading
        eyebrow="Protected technical workspace"
        title="Setup & validation"
        description="Commission models, reconstruction, and inspection settings through a controlled versioned workflow."
        action={<StatusBadge label="Technical mode" tone="info" />}
      />
      <Surface className="setup-workflow">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Commissioning path</p>
            <h2>Configure with confidence</h2>
          </div>
          <span className="setup-workflow__note">Available in Task 16</span>
        </div>
        <div className="setup-steps">
          {setupAreas.map((area) => (
            <article className="setup-step" key={area.title}>
              <span className="setup-step__number">{area.step}</span>
              <span className="setup-step__icon">
                <Icon name={area.icon} />
              </span>
              <h3>{area.title}</h3>
              <p>{area.description}</p>
            </article>
          ))}
        </div>
      </Surface>
      <div className="information-banner">
        <Icon name="shield" />
        <div>
          <strong>Production-safe by design</strong>
          <span>
            Draft settings never modify the active pipeline. Validation and approval are
            explicit steps.
          </span>
        </div>
      </div>
    </div>
  )
}
