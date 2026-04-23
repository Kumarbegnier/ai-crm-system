import { createContext, useContext, ReactNode, useState } from 'react'
import { useLocalStorage } from '../hooks/useLocalStorage'
import { Message } from '../types'

interface ChatContextType {
  messages: Message[]
  addMessage: (message: Message) => void
  loading: boolean
  setLoading: (loading: boolean) => void
  dark: boolean
  setDark: (dark: boolean) => void
}

const ChatContext = createContext<ChatContextType | undefined>(undefined)

export function ChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useLocalStorage<Message[]>('chat-messages', [])
  const [loading, setLoading] = useState<boolean>(false)
  const [dark, setDark] = useState<boolean>(false)

  const addMessage = (message: Message) => {
    setMessages(prev => [...prev, message])
  }

  return (
    <ChatContext.Provider value={{
      messages,
      addMessage,
      loading,
      setLoading,
      dark,
      setDark
    }}>
      {children}
    </ChatContext.Provider>
  )
}

export const useChat = () => {
  const context = useContext(ChatContext)
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider')
  }
  return context
}

