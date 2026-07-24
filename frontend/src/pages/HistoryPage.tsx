import { Link } from 'react-router'

import { Icon } from '../components/Icon'
import { PageHeading, Surface } from '../components/Primitives'

export function HistoryPage() {
  return (
    <div className="page">
      <PageHeading
        eyebrow="Run mode"
        title="Previous inspections"
        description="Each saved result represents one complete acquisition cycle of 16 images."
        action={
          <Link className="return-current-link" to="/run">
            <Icon name="disc" />
            Current run
          </Link>
        }
      />
      <Surface className="empty-state">
        <span className="empty-state__icon">
          <Icon name="archive" />
        </span>
        <p className="eyebrow">No completed cycles</p>
        <h2>Inspection results will appear here</h2>
        <p>
          A completed cycle will contain its reconstructed disc, final result,
          detected defects, and original acquisition evidence.
        </p>
      </Surface>
    </div>
  )
}
