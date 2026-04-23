// import { useChat } from '../../contexts/ChatContext'
import { useWebSocket } from '../../hooks/useWebSocket'
import { Message } from '../../types'
import { Send } from 'lucide-react'
import { useState } from 'react'

interface Props {
  onSend: (message: string) => void
}

export function InputArea({ onSend }: Props) {
// Removed unused - use local state
  const { send, isConnected } = useWebSocket(import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws')
  const [value, setValue] = useState('')

  const handleSend = () => {
    if (!value.trim() || !isConnected) return

    const message: Message = {
      role: 'user',
      text: value,
      timestamp: new Date().toLocaleTimeString()
    }

onSend(message.text)
    send(value)
    setValue('')
  }

  return (
    <div className="p-4 bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm border-t border-slate-200 dark:border-slate-700 rounded-b-2xl shadow-lg">
      <div className="max-w-4xl mx-auto flex gap-3">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Type your HCP interaction..."
          className="flex-1 px-5 py-4 text-lg bg-slate-100 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-3xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none placeholder-slate-500 dark:placeholder-slate-400 transition-all"
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSend())}
          disabled={!isConnected}
        />
        <button
          onClick={handleSend}
          disabled={!isConnected || !value.trim()}
          className="p-4 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-3xl shadow-lg hover:shadow-xl transition-all flex items-center gap-2 text-white"
        >
          <Send className="w-5 h-5" />
        </button>
      </div>
      {!isConnected && (
        <p className="text-center text-sm text-slate-500 mt-2">
          🔌 Connecting to AI Agent...
        </p>
      )}
    </div>
  )
}

