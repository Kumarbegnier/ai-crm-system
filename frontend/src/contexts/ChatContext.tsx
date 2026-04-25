import { createContext, useContext, ReactNode, useState, useCallback } from 'react'
import { useLocalStorage } from '../hooks/useLocalStorage'
import { Message } from '../types'

interface ChatContextType {
  messages: Message[]
  addMessage: (message: Omit<Message, 'id'>) => void
  appendToLastAssistant: (token: string) => void
  clearMessages: () => void
  loading: boolean
  setLoading: (loading: boolean) => void
  dark: boolean
  setDark: (dark: boolean) => void
}

const ChatContext = createContext<ChatContextType | undefined>(undefined)

const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches

const newId = () => crypto.randomUUID()

// ---------------------------------------------------------------------------
// Convert structured JSON action envelopes into human-readable chat text.
// ---------------------------------------------------------------------------
function parseAgentToken(token: string): string {
  try {
    const msg = JSON.parse(token)
    if (!msg.action) return token

    const { action, status, result, params } = msg

    if (status === 'error' || action === 'ERROR' || action === 'REJECTED') {
      return `⚠️ ${result?.message ?? 'Something went wrong.'}`
    }
    if (status === 'timeout') {
      return '⏱️ Request timed out. Please try again.'
    }
    if (status === 'ask') {
      return `🤖 ${result?.message ?? 'I need more information.'}`
    }

    switch (action) {

      case 'CREATE_HCP':
        return `✅ HCP **${params?.name}** saved (ID: ${result?.hcp_id})`

      case 'LOG_INTERACTION':
        return `✅ Logged interaction for **${params?.hcp_name}** (ID: ${result?.interaction_id})`

      case 'GET_HCP_HISTORY': {
        const history: {
          id: number; notes: string; interaction_type?: string
          interaction_channel?: string; interaction_date?: string
          sentiment?: string; product_discussed?: string
          outcome?: string; follow_up_required?: number; follow_up_date?: string
        }[] = result?.history ?? []
        if (!history.length) return `📭 No interactions found for **${params?.hcp_name}**.`
        const lines = history.map(h => [
          `• [${h.interaction_date ?? h.id}] ${h.interaction_type ?? 'call'}${h.interaction_channel ? ` via ${h.interaction_channel}` : ''}`,
          `  ${h.notes}`,
          h.product_discussed ? `  💊 ${h.product_discussed}` : '',
          h.sentiment         ? `  ${h.sentiment === 'positive' ? '😊' : h.sentiment === 'negative' ? '😟' : '😐'} ${h.sentiment}` : '',
          h.outcome           ? `  📌 ${h.outcome}` : '',
          h.follow_up_required ? `  🔔 Follow-up: ${h.follow_up_date ?? 'TBD'}` : '',
        ].filter(Boolean).join('\n')).join('\n')
        return `📋 History for **${params?.hcp_name}**:\n${lines}`
      }

      case 'GET_HCP_PROFILE': {
        const p = result?.profile
        if (!p) return `📭 No profile found for **${params?.hcp_name}**.`
        return [
          `👤 **${p.name}**`,
          p.specialty     ? `🏥 Specialty: ${p.specialty}${p.sub_specialty ? ` → ${p.sub_specialty}` : ''}` : '',
          p.qualification ? `🎓 Qualification: ${p.qualification}` : '',
          p.organization  ? `🏢 Organization: ${p.organization}${p.department ? `, ${p.department}` : ''}` : '',
          (p.city || p.state) ? `📍 Location: ${[p.city, p.state, p.country].filter(Boolean).join(', ')}` : '',
          p.phone         ? `📞 ${p.phone}` : '',
          p.email         ? `✉️ ${p.email}` : '',
          `📊 Engagement: ${p.engagement_score} | Interactions: ${p.total_interactions}`,
          `🔖 Priority: ${p.priority} | Status: ${p.status}`,
          p.last_interaction_date ? `🕒 Last interaction: ${p.last_interaction_date}` : '',
        ].filter(Boolean).join('\n')
      }

      case 'LIST_HCPS': {
        const hcps: { name: string; specialty?: string; priority?: string }[] = result?.hcps ?? []
        if (!hcps.length) return '📭 No HCPs registered yet.'
        const lines = hcps.map(h =>
          `• ${h.name}${h.specialty ? ` — ${h.specialty}` : ''}${h.priority ? ` [${h.priority}]` : ''}`
        ).join('\n')
        return `👥 Registered HCPs (${hcps.length}):\n${lines}`
      }

      case 'RECOMMEND_HCPS': {
        const recs: {
          name: string; specialty?: string; ai_score: number
          recency_component?: number; frequency_component?: number
          last_interaction_date?: string; last_product?: string
          days_since_visit?: number; overdue_followups?: number
        }[] = result?.recommendations ?? []
        if (!recs.length) return '📭 No recommendations available yet.'
        const lines = recs.map((r, i) => [
          `${i + 1}. **${r.name}**${r.specialty ? ` (${r.specialty})` : ''}`,
          `   🤖 AI Score: **${r.ai_score}** (recency: ${r.recency_component}, frequency: ${r.frequency_component})`,
          r.days_since_visit != null && r.days_since_visit < 999
            ? `   📅 Last visit: ${r.days_since_visit} day${r.days_since_visit !== 1 ? 's' : ''} ago`
            : '   📅 Never visited',
          r.last_product ? `   💊 Discussed: ${r.last_product}` : '',
          r.overdue_followups ? `   ⚠️ Follow-up overdue` : '',
        ].filter(Boolean).join('\n')).join('\n')
        const top = recs[0]
        const suggestion = top?.overdue_followups
          ? `\n\n👉 Start with **${top.name}** (overdue follow-up)`
          : `\n\n👉 Start with **${top?.name}** (highest AI score)`
        return `🌟 AI-Prioritized HCPs to visit today:\n\n${lines}${suggestion}`
      }

      case 'GET_INACTIVE_HCPS': {
        const inactive: { name: string; specialty?: string; last_interaction?: string | null }[] = result?.inactive_hcps ?? []
        if (!inactive.length) return `✅ No inactive HCPs in the last ${params?.days} days.`
        const lines = inactive.map(h =>
          `• ${h.name}${h.specialty ? ` (${h.specialty})` : ''} — last seen: ${h.last_interaction ?? 'never'}`
        ).join('\n')
        return `😴 Inactive HCPs (>${params?.days} days):\n${lines}`
      }

      case 'GET_FOLLOWUPS': {
        const followups: {
          hcp_name: string; interaction_type?: string
          notes: string; follow_up_date?: string; outcome?: string
          product_discussed?: string; is_overdue?: number
        }[] = result?.followups ?? []
        if (!followups.length) return '✅ No pending follow-ups.'
        const overdue = followups.filter(f => f.is_overdue)
        const lines = followups.map(f => [
          `${f.is_overdue ? '🔴' : '🔵'} **${f.hcp_name}** — ${f.interaction_type ?? 'call'}${f.is_overdue ? ' ⚠️ OVERDUE' : ''}`,
          `  ${f.notes}`,
          f.product_discussed ? `  💊 ${f.product_discussed}` : '',
          f.outcome           ? `  📌 ${f.outcome}` : '',
          f.follow_up_date    ? `  🔔 Due: ${f.follow_up_date}` : '  🔔 No date set',
        ].filter(Boolean).join('\n')).join('\n')
        const header = overdue.length
          ? `🔔 Follow-ups (${followups.length} total, ${overdue.length} overdue):`
          : `🔔 Pending Follow-ups (${followups.length}):`
        return `${header}\n${lines}`
      }

      case 'FILTER_BY_PRIORITY': {
        const hcps: { name: string; specialty?: string; engagement_score: number }[] = result?.hcps ?? []
        if (!hcps.length) return `📭 No **${params?.priority}** priority HCPs found.`
        const lines = hcps.map(h =>
          `• ${h.name}${h.specialty ? ` — ${h.specialty}` : ''} (score: ${h.engagement_score})`
        ).join('\n')
        return `🔖 **${params?.priority?.toUpperCase()}** priority HCPs (${hcps.length}):\n${lines}`
      }

      case 'GET_DAILY_SUMMARY': {
        const s = result?.summary
        if (!s) return '💭 No summary available.'
        const lines = [
          `📅 **Daily Summary — ${s.date}**`,
          '',
          `✔️ Interactions logged: **${s.total_interactions}**`,
          `👥 HCPs visited: **${s.unique_hcps_visited}**`,
          `🔔 Follow-ups scheduled today: **${s.followups_scheduled_today}**`,
          s.overdue_followups ? `⚠️ Overdue follow-ups: **${s.overdue_followups}**` : '',
          '',
          s.top_hcp
            ? `🏆 Top HCP: **${s.top_hcp.name}**${s.top_hcp.specialty ? ` (${s.top_hcp.specialty})` : ''} — ${s.top_hcp.cnt} interaction${s.top_hcp.cnt !== 1 ? 's' : ''}`
            : '',
          s.top_segment
            ? `📈 Top segment: **${s.top_segment.specialty}** (${s.top_segment.cnt} interaction${s.top_segment.cnt !== 1 ? 's' : ''})`
            : '',
          s.top_segment
            ? `\n👉 Recommendation: Focus on **${s.top_segment.specialty}** cluster tomorrow`
            : '',
        ].filter(Boolean).join('\n')
        return lines
      }

      case 'CREATE_TAG':
        return `🏷️ Tag **${params?.name}** created (ID: ${result?.tag_id})`

      case 'ASSIGN_TAG':
        return `✅ Tag **${params?.tag_name}** assigned to **${params?.hcp_name}**`

      case 'GET_HCP_TAGS': {
        const tags: { name: string; category?: string; confidence_score?: number }[] = result?.tags ?? []
        if (!tags.length) return `📭 No tags found for **${params?.hcp_name}**.`
        const lines = tags.map(t =>
          `• ${t.name}${t.category ? ` [${t.category}]` : ''}${t.confidence_score != null ? ` (${Math.round(t.confidence_score * 100)}%)` : ''}`
        ).join('\n')
        return `🏷️ Tags for **${params?.hcp_name}**:\n${lines}`
      }

      case 'SEARCH_BY_TAG': {
        const hcps: { name: string; specialty?: string; engagement_score?: number }[] = result?.hcps ?? []
        if (!hcps.length) return `📭 No HCPs found with tag **${params?.tag_name}**.`
        const lines = hcps.map(h =>
          `• ${h.name}${h.specialty ? ` — ${h.specialty}` : ''}`
        ).join('\n')
        return `🔍 HCPs tagged **${params?.tag_name}** (${hcps.length}):\n${lines}`
      }

      case 'BOOK_APPOINTMENT': {
        const appt = result
        if (appt?.status === 'booked') {
          return `✅ Appointment booked!\n👤 **${params?.doctor}**\n📅 ${params?.date}\n⏰ ${params?.time}\n🆔 ID: ${appt.appointment_id}`
        }
        return `⚠️ Could not book appointment.`
      }

      case 'LIST_APPOINTMENTS': {
        const appts: { hcp_name: string; date: string; time: string; status: string; notes?: string }[] = result?.appointments ?? []
        if (!appts.length) return '📭 No appointments found.'
        const lines = appts.map(a =>
          `• **${a.hcp_name}** — ${a.date} at ${a.time} [${a.status}]${a.notes ? ` 📝 ${a.notes}` : ''}`
        ).join('\n')
        return `📅 Appointments (${appts.length}):\n${lines}`
      }

      case 'SEARCH_NOTES': {
        const results: { id: string; score: number; metadata: Record<string, string> }[] = result?.results ?? []
        if (!results.length) return '🔍 No relevant notes found.'
        const lines = results.map((r, i) =>
          `${i + 1}. **${r.metadata.hcp_name}** (score: ${Math.round(r.score * 100)}%)\n   📝 ${r.id}`
        ).join('\n')
        return `🔍 Semantic Search Results for "${params?.query}":\n${lines}`
      }

      case 'GENERATE_SUMMARY': {
        const summary = result?.summary
        const count = result?.interaction_count ?? 0
        return `📝 AI Summary for **${params?.hcp_name}** (${count} interactions):\n\n${summary}`
      }

      case 'GENERATE_EMAIL': {
        const email = result?.email
        return `✉️ Draft Follow-up Email for **${params?.hcp_name}**:\n\n${email}`
      }

      default:
        return token
    }
  } catch {
    return token
  }
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useLocalStorage<Message[]>('chat-messages', [])
  const [dark, setDark] = useLocalStorage<boolean>('chat-dark', systemPrefersDark)
  const [loading, setLoading] = useState(false)

  const addMessage = useCallback((message: Omit<Message, 'id'>) => {
    // Cap at 200 messages to prevent localStorage quota errors
    setMessages(prev => {
      const next = [...prev, { ...message, id: newId() }]
      return next.length > 200 ? next.slice(-200) : next
    })
  }, [setMessages])

  const clearMessages = useCallback(() => {
    setMessages([])
  }, [setMessages])

  const appendToLastAssistant = useCallback((token: string) => {
    const display = parseAgentToken(token)
    setMessages(prev => {
      const last = prev[prev.length - 1]
      if (last?.role === 'assistant') {
        // Mutate last bubble in-place — keep its stable id
        return [...prev.slice(0, -1), { ...last, text: last.text + display }]
      }
      // First token of a new assistant turn — create bubble and clear loading
      setLoading(false)
      return [...prev, { id: newId(), role: 'assistant', text: display, timestamp: new Date().toLocaleTimeString() }]
    })
  }, [setMessages, setLoading])

  return (
    <ChatContext.Provider value={{ messages, addMessage, appendToLastAssistant, clearMessages, loading, setLoading, dark, setDark }}>
      {children}
    </ChatContext.Provider>
  )
}

export const useChat = () => {
  const context = useContext(ChatContext)
  if (!context) throw new Error('useChat must be used within a ChatProvider')
  return context
}

