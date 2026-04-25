import { useState, useRef, useEffect, useCallback } from 'react'
import { Moon, Sun, Trash2, Wifi, WifiOff, PlusSquare } from 'lucide-react'
import { ChatBox } from './components/ChatBox/ChatBox'
import { InputArea } from './components/InputArea/InputArea'
import { LogInteractionScreen } from './components/LogInteraction/LogInteractionScreen'
import { useWebSocket } from './hooks/useWebSocket'
import { useChat } from './contexts/ChatContext'

type View = 'chat' | 'log' | 'appointments' | 'analytics'

export default function App() {
  const { messages, addMessage, appendToLastAssistant, loading, setLoading, dark, setDark, clearMessages } = useChat()
  const chatRef = useRef<HTMLDivElement>(null)
  const [isNearBottom, setIsNearBottom] = useState(true)
  const [view, setView] = useState<View>('chat')
  const scrollThrottleRef = useRef(false)

  const scrollToBottom = useCallback(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: 'smooth' })
  }, [])

  useEffect(() => {
    if (isNearBottom) scrollToBottom()
  }, [messages, isNearBottom, scrollToBottom])

  const handleScroll = useCallback(() => {
    if (scrollThrottleRef.current) return
    scrollThrottleRef.current = true
    setTimeout(() => {
      if (chatRef.current) {
        const { scrollTop, scrollHeight, clientHeight } = chatRef.current
        setIsNearBottom(scrollHeight - scrollTop - clientHeight < 100)
      }
      scrollThrottleRef.current = false
    }, 100)
  }, [])

  const handleEnd = useCallback(() => setLoading(false), [setLoading])

  const { isConnected, send } = useWebSocket(
    import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws',
    appendToLastAssistant,
    handleEnd
  )

  useEffect(() => {
    if (!isConnected) setLoading(false)
  }, [isConnected, setLoading])

  // When chat send is triggered from LogInteraction, switch to chat view
  const handleSend = useCallback((messageText: string) => {
    addMessage({ role: 'user', text: messageText, timestamp: new Date().toLocaleTimeString() })
    setLoading(true)
    send(messageText)
    setView('chat')
  }, [addMessage, setLoading, send])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])

  return (
    <div className="h-screen flex flex-col bg-slate-50 dark:bg-slate-950 transition-colors duration-300">

      {/* Header */}
      <header className="flex-none flex items-center justify-between px-6 py-3 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center text-white text-lg shadow">
            🏥
          </div>
          <div>
            <h1 className="text-base font-semibold text-slate-900 dark:text-white leading-tight">
              Healthcare Professionals
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">AI-Powered CRM Assistant</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Nav tabs */}
          <div className="flex rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700 text-xs font-medium">
            <button
              onClick={() => setView('chat')}
              className={`px-3 py-1.5 transition-colors ${
                view === 'chat'
                  ? 'bg-brand-500 text-white'
                  : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
              }`}
            >
              Chat
            </button>
            <button
              onClick={() => setView('log')}
              className={`px-3 py-1.5 transition-colors flex items-center gap-1 ${
                view === 'log'
                  ? 'bg-brand-500 text-white'
                  : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
              }`}
            >
              <PlusSquare className="w-3 h-3" /> Log
            </button>
            <button
              onClick={() => setView('appointments')}
              className={`px-3 py-1.5 transition-colors ${
                view === 'appointments'
                  ? 'bg-brand-500 text-white'
                  : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
              }`}
            >
              Appointments
            </button>
            <button
              onClick={() => setView('analytics')}
              className={`px-3 py-1.5 transition-colors ${
                view === 'analytics'
                  ? 'bg-brand-500 text-white'
                  : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
              }`}
            >
              Analytics
            </button>
          </div>

          {/* Connection badge */}
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
            isConnected
              ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
              : 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400'
          }`}>
            {isConnected
              ? <><Wifi className="w-3 h-3" /> Connected</>
              : <><WifiOff className="w-3 h-3" /> Reconnecting</>
            }
          </span>

          {messages.length > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-xs text-slate-500 dark:text-slate-400 font-medium">
              {messages.length} msg{messages.length !== 1 ? 's' : ''}
            </span>
          )}

          {messages.length > 0 && (
            <button onClick={clearMessages} title="Clear chat"
              className="p-2 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors">
              <Trash2 className="w-4 h-4" />
            </button>
          )}

          <button onClick={() => setDark(!dark)}
            title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
            {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 flex overflow-hidden w-full mx-auto" style={{maxWidth: '1280px'}}>

        {/* Chat panel — always mounted, hidden when log view is active on small screens */}
        <div className={`flex flex-col overflow-hidden transition-all min-w-0 ${
          view === 'log' ? 'hidden lg:flex lg:flex-1' : 'flex-1'
        }`}>
          <div
            ref={chatRef}
            className="flex-1 overflow-y-auto scrollbar-thin px-4 py-6 w-full"
            onScroll={handleScroll}
          >
            <ChatBox
              messages={messages}
              loading={loading}
              scrollToBottom={scrollToBottom}
              isNearBottom={isNearBottom}
              onHintClick={handleSend}
            />
          </div>
          <InputArea onSend={handleSend} isConnected={isConnected} loading={loading} />
        </div>

        {/* Log Interaction panel */}
        {view === 'log' && (
          <div className="flex-1 lg:max-w-md lg:border-l border-slate-200 dark:border-slate-800 flex flex-col overflow-hidden bg-white dark:bg-slate-900">
            <LogInteractionScreen
              onChatSend={handleSend}
              isConnected={isConnected}
              loading={loading}
            />
          </div>
        )}

        {/* Appointments panel */}
        {view === 'appointments' && (
          <div className="flex-1 lg:max-w-md lg:border-l border-slate-200 dark:border-slate-800 flex flex-col overflow-hidden bg-white dark:bg-slate-900 p-4 gap-3">
            <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Appointments</h2>
            {[
              'List my appointments',
              'Book Dr. Sharma tomorrow 10:00',
              'Cancel appointment',
            ].map(hint => (
              <button
                key={hint}
                onClick={() => handleSend(hint)}
                className="text-left text-xs px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-brand-400 hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
              >
                📅 {hint}
              </button>
            ))}
          </div>
        )}

        {/* Analytics panel */}
        {view === 'analytics' && (
          <div className="flex-1 lg:max-w-md lg:border-l border-slate-200 dark:border-slate-800 flex flex-col overflow-hidden bg-white dark:bg-slate-900 p-4 gap-3">
            <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Analytics & AI</h2>
            {[
              'Recommend HCPs to visit today',
              'Show today summary',
              'Summarize Dr. Sharma last 5 interactions',
              'Generate follow-up email to Dr. Kumar',
              'Search notes about cholesterol drugs',
            ].map(hint => (
              <button
                key={hint}
                onClick={() => handleSend(hint)}
                className="text-left text-xs px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-brand-400 hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
              >
                🤖 {hint}
              </button>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
