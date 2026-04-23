import { Message } from '../../types'

interface Props {
  messages: Message[]
  loading: boolean
  scrollToBottom: () => void
  isNearBottom: boolean
}

export function ChatBox({ messages, loading, scrollToBottom, isNearBottom }: Props) {
  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 rounded-2xl shadow-2xl">
      {messages.map((msg, i) => (
        <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div className={`max-w-[70%] p-4 rounded-2xl shadow-lg ${
            msg.role === 'user'
              ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white'
              : 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white'
          }`}>
            <p className="text-sm leading-relaxed">{msg.text}</p>
            <p className="text-xs opacity-70 mt-1">{msg.timestamp}</p>
          </div>
        </div>
      ))}
      {loading && (
        <div className="flex justify-start">
          <div className="flex space-x-1">
            <div className="w-3 h-3 bg-slate-400 rounded-full animate-bounce" />
            <div className="w-3 h-3 bg-slate-400 rounded-full animate-bounce [animation-delay:0.1s]" />
            <div className="w-3 h-3 bg-slate-400 rounded-full animate-bounce [animation-delay:0.2s]" />
          </div>
        </div>
      )}
      {!isNearBottom && (
        <button 
          onClick={scrollToBottom}
          className="fixed bottom-24 right-6 bg-blue-500 text-white p-3 rounded-full shadow-lg hover:bg-blue-600 transition-all"
        >
          ↓
        </button>
      )}
    </div>
  )
}

