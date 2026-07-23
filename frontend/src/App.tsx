const layers = [
  'Electron desktop shell',
  'React operator interface',
  'FastAPI local backend',
  'Isolated production workers',
]

export function App() {
  return (
    <main className="foundation">
      <section className="foundation__panel" aria-labelledby="foundation-title">
        <p className="foundation__eyebrow">Standalone Production Inspection</p>
        <h1 id="foundation-title">Application foundation ready</h1>
        <p className="foundation__summary">
          The secure desktop, frontend, and backend foundations are connected.
          Production features will be added one approved task at a time.
        </p>
        <ul className="foundation__layers" aria-label="Application layers">
          {layers.map((layer) => (
            <li key={layer}>{layer}</li>
          ))}
        </ul>
        <p className="foundation__status">
          <span aria-hidden="true" />
          Foundation status: ready
        </p>
      </section>
    </main>
  )
}
