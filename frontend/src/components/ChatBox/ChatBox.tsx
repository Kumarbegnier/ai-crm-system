import { memo } from 'react'
import { ChevronDown, Bot, User } from 'lucide-react'
import { Message } from '../../types'

interface Props {
  messages: Message[]
  loading: boolean
  scrollToBottom: () => void
  isNearBottom: boolean
  onHintClick: (hint: string) => void
}

function renderText(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, i) =>
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>
      : <span key={i}>{part}</span>
  )
}

const MessageBubble = memo(
  ({ msg }: { msg: Message }) => {
    const isUser = msg.role === 'user'
    return (
      <div className={`flex items-end gap-2.5 animate-slide-up ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        <div className={`flex-none w-7 h-7 rounded-full flex items-center justify-center shadow-sm ${
          isUser
            ? 'bg-gradient-to-br from-brand-500 to-purple-600'
            : 'bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600'
        }`}>
          {isUser
            ? <User className="w-3.5 h-3.5 text-white" />
            : <Bot className="w-3.5 h-3.5 text-brand-500 dark:text-brand-400" />
          }
        </div>

        <div className={`group max-w-[75%] flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
          <div className={`px-4 py-2.5 rounded-2xl shadow-sm text-sm leading-relaxed whitespace-pre-wrap ${
            isUser
              ? 'bg-gradient-to-br from-brand-500 to-purple-600 text-white rounded-br-sm'
              : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 border border-slate-100 dark:border-slate-700 rounded-bl-sm'
          }`}>
            {renderText(msg.text)}
          </div>
          {msg.timestamp && (
            <span className="text-[10px] text-slate-400 dark:text-slate-500 px-1 opacity-0 group-hover:opacity-100 transition-opacity">
              {msg.timestamp}
            </span>
          )}
        </div>
      </div>
    )
  },
  (prev, next) => prev.msg.text === next.msg.text && prev.msg.timestamp === next.msg.timestamp
)
MessageBubble.displayName = 'MessageBubble'

function TypingIndicator() {
  return (
    <div className="flex items-end gap-2.5">
      <div className="flex-none w-7 h-7 rounded-full bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 flex items-center justify-center shadow-sm">
        <Bot className="w-3.5 h-3.5 text-brand-500 dark:text-brand-400" />
      </div>
      <div className="bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
        <div className="flex gap-1 items-center h-4">
          {[0, 1, 2].map(i => (
            <span
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-slate-400 dark:bg-slate-500 animate-bounce-dot"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

const HINTS = [
  'Recommend HCPs to visit today',
  'Show today summary',
  'Who needs follow-up?',
  'Book Dr. Kumar tomorrow 14:30',
  'Met Dr. Sharma, discussed Lipitor, follow up next week',
  'Summarize Dr. Sharma last 5 interactions',
  'Search notes about cholesterol drugs',
]

function EmptyState({ onHintClick }: { onHintClick: (hint: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-center py-16">
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center text-3xl shadow-lg">
        🏥
      </div>
      <div>
        <p className="text-slate-700 dark:text-slate-200 font-semibold text-lg">Healthcare Professionals CRM</p>
        <p className="text-slate-400 dark:text-slate-500 text-sm mt-1 max-w-xs">
          Ask me to log interactions, look up HCP profiles, check follow-ups, or get recommendations.
        </p>
      </div>
      <div className="flex flex-wrap gap-2 justify-center mt-2">
        {HINTS.map(hint => (
          <button
            key={hint}
            onClick={() => onHintClick(hint)}
            className="px-3 py-1.5 rounded-full bg-slate-100 dark:bg-slate-800 text-xs text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700 hover:border-brand-500 hover:text-brand-600 dark:hover:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-900/20 transition-colors cursor-pointer"
          >
            {hint}
          </button>
        ))}
      </div>
    </div>
  )
}

export function ChatBox({ messages, loading, scrollToBottom, isNearBottom, onHintClick }: Props) {
  return (
    <div className="relative flex flex-col gap-4 min-h-full w-full">
      {messages.length === 0 && !loading
        ? <EmptyState onHintClick={onHintClick} />
        : messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)
      }
      {loading && <TypingIndicator />}

      {!isNearBottom && (
        <button
          onClick={scrollToBottom}
          className="sticky bottom-4 self-center z-10 w-9 h-9 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 rounded-full shadow-lg hover:shadow-xl hover:text-brand-500 dark:hover:text-brand-400 transition-all flex items-center justify-center"
          aria-label="Scroll to bottom"
        >
          <ChevronDown className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}
