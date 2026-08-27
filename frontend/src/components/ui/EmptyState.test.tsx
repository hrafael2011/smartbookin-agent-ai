import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { EmptyState } from './EmptyState'

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(<EmptyState icon={<span>🔍</span>} title="No results" description="No items found" />)
    expect(screen.getByText('No results')).toBeInTheDocument()
    expect(screen.getByText('No items found')).toBeInTheDocument()
  })

  it('renders action button when actionLabel and onAction are provided', () => {
    const onAction = vi.fn()
    render(
      <EmptyState
        icon={<span>➕</span>}
        title="Empty"
        description="Nothing here"
        actionLabel="Add Item"
        onAction={onAction}
      />
    )
    const button = screen.getByRole('button', { name: /add item/i })
    expect(button).toBeInTheDocument()
  })

  it('calls onAction when button is clicked', async () => {
    const user = userEvent.setup()
    const onAction = vi.fn()
    render(
      <EmptyState
        icon={<span>➕</span>}
        title="Empty"
        description="Nothing here"
        actionLabel="Add Item"
        onAction={onAction}
      />
    )
    await user.click(screen.getByRole('button'))
    expect(onAction).toHaveBeenCalledTimes(1)
  })

  it('does not render button when actionLabel is not provided', () => {
    render(<EmptyState icon={<span>🔍</span>} title="No results" description="No items found" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
