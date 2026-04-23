import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { InputArea } from '../src/components/InputArea/InputArea'
import { ChatProvider } from '../src/contexts/ChatContext'

// Mock WS
global.WebSocket = vi.fn(() => ({
  readyState: WebSocket.OPEN,
  close: vi.fn(),
  send: vi.fn(),
  onopen: vi.fn(),
  onclose: vi.fn(),
  onmessage: vi.fn()
})) as any

describe('InputArea', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders input and send button', () => {
    render(
      <ChatProvider>
        <InputArea onSend={vi.fn()} />
      </ChatProvider>
    )

    expect(screen.getByPlaceholderText(/Type your HCP interaction/i)).toBeInTheDocument()
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('sends message on button click', async () => {
    const onSend = vi.fn()
    render(
      <ChatProvider>
        <InputArea onSend={onSend} />
      </ChatProvider>
    )

    const input = screen.getByPlaceholderText(/Type your HCP interaction/i)
    const button = screen.getByRole('button')

    fireEvent.change(input, { target: { value: 'Test HCP interaction' } })
    fireEvent.click(button)

    await waitFor(() => {
      expect(onSend).toHaveBeenCalledWith(expect.objectContaining({
        role: 'user',
        text: 'Test HCP interaction'
      }))
    })
  })

  it('handles enter key', async () => {
    const onSend = vi.fn()
    render(
      <ChatProvider>
        <InputArea onSend={onSend} />
      </ChatProvider>
    )

    const input = screen.getByPlaceholderText(/Type your HCP interaction/i)
    fireEvent.change(input, { target: { value: 'Test' } })
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' })

    await waitFor(() => {
      expect(onSend).toHaveBeenCalled()
    })
  })

  it('shows connecting message when not connected', () => {
    ;(global.WebSocket as any).mockImplementation(() => ({
      readyState: WebSocket.CONNECTING,
      close: vi.fn(),
      send: vi.fn()
    }))

    render(
      <ChatProvider>
        <InputArea onSend={vi.fn()} />
      </ChatProvider>
    )

    expect(screen.getByText(/Connecting to AI Agent/i)).toBeInTheDocument()
  })

  it('disables input and button when not connected', () => {
    ;(global.WebSocket as any).mockImplementation(() => ({
      readyState: WebSocket.CLOSED,
      close: vi.fn(),
      send: vi.fn()
    }))

    render(
      <ChatProvider>
        <InputArea onSend={vi.fn()} />
      </ChatProvider>
    )

    const input = screen.getByPlaceholderText(/Type your HCP interaction/i)
    const button = screen.getByRole('button')

    expect(input).toBeDisabled()
    expect(button).toBeDisabled()
  })
})

