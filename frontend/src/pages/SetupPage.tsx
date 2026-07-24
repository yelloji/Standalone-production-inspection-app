import { Icon } from '../components/Icon'
import { ModelLibrary } from '../components/ModelLibrary'
import { PageHeading, StatusBadge, Surface } from '../components/Primitives'

const setupAreas = [
  {
    title: 'Inspection pipeline',
    description: 'Create a versioned configuration without changing production.',
    icon: 'settings' as const,
    step: 'Next',
  },
  {
    title: 'Offline validation',
    description: 'Prove accuracy and performance before approval.',
    icon: 'shield' as const,
    step: 'Later',
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
      <ModelLibrary />
      <Surface className="setup-workflow">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Coming next</p>
            <h2>Complete the production pipeline</h2>
          </div>
          <span className="setup-workflow__note">Task 16 continues</span>
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
