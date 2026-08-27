import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Card, CardHeader, CardTitle, CardContent } from './Card'

describe('Card', () => {
  it('renders children', () => {
    render(<Card>Card content</Card>)
    expect(screen.getByText('Card content')).toBeInTheDocument()
  })

  it('renders with custom className', () => {
    render(<Card className="custom-class">Content</Card>)
    expect(screen.getByText('Content').className).toContain('custom-class')
  })
})

describe('CardHeader', () => {
  it('renders children', () => {
    render(<CardHeader>Header</CardHeader>)
    expect(screen.getByText('Header')).toBeInTheDocument()
  })
})

describe('CardTitle', () => {
  it('renders as h3', () => {
    render(<CardTitle>Title</CardTitle>)
    const heading = screen.getByRole('heading', { name: /title/i })
    expect(heading).toBeInTheDocument()
    expect(heading.tagName).toBe('H3')
  })
})

describe('CardContent', () => {
  it('renders children', () => {
    render(<CardContent>Content body</CardContent>)
    expect(screen.getByText('Content body')).toBeInTheDocument()
  })
})
