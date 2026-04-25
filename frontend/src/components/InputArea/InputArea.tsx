import { useCallback, useRef, useState } from 'react'
import { Send, Loader2 } from 'lucide-react'

interface Props {
  onSend: (message: string) => void
  isConnected: boolean
  loading: boolean
}

const MAX_LENGTH = 1000

export function InputArea({ onSend, isConnected, loading }: Props) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const disabled = !isConnected || loading
  const remaining = MAX_LENGTH - value.length
  const nearLimit = remaining <= 100

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    // Reset textarea height
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }, [value, disabled, onSend])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value)
    // Auto-grow textarea up to 5 lines
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`
  }

  return (
    <div className="flex-none border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 py-3">
      <div className="max-w-3xl mx-auto">
        <div className={`flex items-end gap-2 rounded-2xl border transition-colors ${
          disabled
            ? 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50'
            : 'border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 focus-within:border-brand-500 dark:focus-within:border-brand-500'
        } shadow-sm px-4 py-2`}>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={loading ? 'Waiting for response...' : 'Ask about HCPs, log interactions, check follow-ups…'}
            disabled={disabled}
            maxLength={MAX_LENGTH}
            rows={1}
            className="flex-1 bg-transparent text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none py-1.5 min-h-[36px] max-h-[140px] leading-relaxed disabled:cursor-not-allowed"
          />
          <div className="flex items-center gap-2 pb-1.5 flex-none">
            {nearLimit && (
              <span className={`text-xs tabular-nums ${remaining <= 20 ? 'text-red-500' : 'text-slate-400'}`}>
                {remaining}
              </span>
            )}
            <button
              onClick={handleSend}
              disabled={disabled || !value.trim()}
              aria-label="Send message"
              className="w-8 h-8 rounded-xl flex items-center justify-center transition-all disabled:opacity-40 disabled:cursor-not-allowed bg-gradient-to-br from-brand-500 to-purple-600 hover:from-brand-600 hover:to-purple-700 text-white shadow-sm hover:shadow-md active:scale-95"
            >
              {loading
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <Send className="w-3.5 h-3.5" />
              }
            </button>
          </div>
        </div>

        <p className="text-center text-[11px] text-slate-400 dark:text-slate-600 mt-2">
          {!isConnected
            ? '🔌 Reconnecting to agent…'
            : 'Press Enter to send · Shift+Enter for new line'
          }
        </p>
      </div>
    </div>
  )
}
