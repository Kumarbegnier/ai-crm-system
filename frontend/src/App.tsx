import { useState, useRef, useEffect, useCallback } from 'react'
import { ChatBox } from './components/ChatBox/ChatBox'
import { InputArea } from './components/InputArea/InputArea'
import { useWebSocket } from './hooks/useWebSocket'
import { useChat } from './contexts/ChatContext'
import { Message } from './types'

export default function App() {
  const { messages, addMessage, loading, setLoading, dark, setDark } = useChat()
  const { isConnected, send } = useWebSocket('ws://localhost:8000/ws')
  const chatRef = useRef<HTMLDivElement>(null)
  const [isNearBottom, setIsNearBottom] = useState(true)

  const scrollToBottom = useCallback(() => {
    chatRef.current?.scrollTo({
      top: chatRef.current.scrollHeight,
      behavior: 'smooth'
    })
  }, [])

  const handleScroll = () => {
    if (!chatRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = chatRef.current
    setIsNearBottom(scrollHeight - scrollTop - clientHeight < 100)
  }

  const handleSend = (messageText: string) => {
    const message: Message = {
      role: 'user',
      text: messageText,
      timestamp: new Date().toLocaleTimeString()
    }
    addMessage(message)
    setLoading(true)
    send(messageText)
  }

  useEffect(() => {
    document.body.className = dark ? 'dark' : ''
  }, [dark])

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-slate-900 dark:to-slate-800 transition-colors p-4">
      <div className="max-w-2xl mx-auto h-screen flex flex-col">
        <header className="p-6 text-center">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-2">
            AI HCP CRM 🤖
          </h1>
          <button
            onClick={() => setDark(!dark)}
            className="px-4 py-2 bg-slate-200 dark:bg-slate-700 rounded-xl hover:bg-slate-300 dark:hover:bg-slate-600 transition-all flex items-center gap-2 mx-auto"
          >
            {dark ? '☀️ Light' : '🌙 Dark'}
          </button>
          <div className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            {isConnected ? '🟢 Connected' : '🔴 Connecting...'}
          </div>
        </header>

        <main className="flex-1 flex flex-col overflow-hidden rounded-3xl shadow-2xl bg-white/80 dark:bg-slate-800/80 backdrop-blur-xl border border-slate-200 dark:border-slate-700 mx-4 mb-4">
          <div 
            ref={chatRef}
            className="flex-1 overflow-y-auto p-8 space-y-6 scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-600"
            onScroll={handleScroll}
          >
            <ChatBox 
              messages={messages} 
              loading={loading} 
              scrollToBottom={scrollToBottom} 
              isNearBottom={isNearBottom}
            />
          </div>
          <InputArea onSend={handleSend} />
        </main>
      </div>
    </div>
  )
}

