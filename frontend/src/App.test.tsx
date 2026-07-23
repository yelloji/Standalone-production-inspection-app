import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { App } from './App'

describe('App foundation', () => {
  it('shows the standalone foundation state', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: 'Application foundation ready' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Foundation status: ready')).toBeInTheDocument()
  })
})
