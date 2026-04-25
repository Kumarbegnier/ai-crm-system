import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { InputArea } from '../src/components/InputArea/InputArea'

describe('InputArea', () => {
  const defaultProps = {
    onSend: vi.fn(),
    isConnected: true,
    loading: false,
  }

  beforeEach(() => vi.clearAllMocks())

  it('renders textarea and send button', () => {
    render(<InputArea {...defaultProps} />)
    expect(screen.getByRole('textbox')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument()
  })

  it('calls onSend with trimmed string on button click', () => {
    render(<InputArea {...defaultProps} />)
    const textarea = screen.getByRole('textbox')
    fireEvent.change(textarea, { target: { value: '  Met Dr. Sharma  ' } })
    fireEvent.click(screen.getByRole('button', { name: /send/i }))
    expect(defaultProps.onSend).toHaveBeenCalledWith('Met Dr. Sharma')
  })

  it('calls onSend on Enter key (not Shift+Enter)', () => {
    render(<InputArea {...defaultProps} />)
    const textarea = screen.getByRole('textbox')
    fireEvent.change(textarea, { target: { value: 'Test message' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })
    expect(defaultProps.onSend).toHaveBeenCalledWith('Test message')
  })

  it('does NOT send on Shift+Enter', () => {
    render(<InputArea {...defaultProps} />)
    const textarea = screen.getByRole('textbox')
    fireEvent.change(textarea, { target: { value: 'Test' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true })
    expect(defaultProps.onSend).not.toHaveBeenCalled()
  })

  it('does NOT send empty or whitespace-only input', () => {
    render(<InputArea {...defaultProps} />)
    const textarea = screen.getByRole('textbox')
    fireEvent.change(textarea, { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: /send/i }))
    expect(defaultProps.onSend).not.toHaveBeenCalled()
  })

  it('disables textarea and button when not connected', () => {
    render(<InputArea {...defaultProps} isConnected={false} />)
    expect(screen.getByRole('textbox')).toBeDisabled()
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
  })

  it('shows reconnecting hint when not connected', () => {
    render(<InputArea {...defaultProps} isConnected={false} />)
    expect(screen.getByText(/reconnecting/i)).toBeInTheDocument()
  })

  it('disables send button while loading', () => {
    render(<InputArea {...defaultProps} loading={true} />)
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
  })

  it('clears textarea after send', () => {
    render(<InputArea {...defaultProps} />)
    const textarea = screen.getByRole('textbox')
    fireEvent.change(textarea, { target: { value: 'Hello' } })
    fireEvent.click(screen.getByRole('button', { name: /send/i }))
    expect(textarea).toHaveValue('')
  })

  it('shows character counter near limit', () => {
    render(<InputArea {...defaultProps} />)
    const textarea = screen.getByRole('textbox')
    // Type 950 chars (1000 - 950 = 50 remaining, which is <= 100 so counter shows)
    fireEvent.change(textarea, { target: { value: 'a'.repeat(950) } })
    expect(screen.getByText('50')).toBeInTheDocument()
  })
})
