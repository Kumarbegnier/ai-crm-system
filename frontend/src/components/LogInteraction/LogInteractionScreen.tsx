import { useState, useCallback } from 'react'
import { Send, Save, FileText, MessageSquare, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'

interface Props {
  onChatSend: (text: string) => void
  isConnected: boolean
  loading: boolean
}

type Tab = 'chat' | 'form'
type Status = 'idle' | 'saving' | 'success' | 'error'

const INTERACTION_TYPES = ['call', 'visit', 'meeting', 'email'] as const
const SENTIMENTS       = ['positive', 'neutral', 'negative'] as const
const OUTCOMES         = ['interested', 'not_interested', 'follow_up_required'] as const

const CHAT_EXAMPLES = [
  'Met Dr. Sharma today, discussed Lipitor, very interested, follow up next week',
  'Called Dr. Patel, not available, will try again tomorrow',
  'Visited Dr. Kumar at Apollo, discussed new drug trial, positive outcome',
  'Show today summary',
  'Who needs follow-up?',
]

const EMPTY_FORM = () => ({
  hcp_name: '', interaction_type: 'call',
  interaction_date: new Date().toISOString().slice(0, 10),
  notes: '', product_discussed: '', sentiment: '', outcome: '',
  follow_up_required: false, follow_up_date: '',
})

export function LogInteractionScreen({ onChatSend, isConnected, loading }: Props) {
  const [tab, setTab]       = useState<Tab>('chat')
  const [status, setStatus] = useState<Status>('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const [chatInput, setChatInput] = useState('')
  const [form, setForm] = useState(() => EMPTY_FORM())

  const set = (key: string, value: string | boolean) =>
    setForm(prev => ({ ...prev, [key]: value }))

  // ── Form submit ──────────────────────────────────────────────────────────
  const handleFormSubmit = useCallback(async () => {
    if (!form.hcp_name.trim() || !form.notes.trim()) return
    setStatus('saving')
    try {
      const body: Record<string, unknown> = {
        ...form,
        // Convert date-only string to ISO timestamp the backend expects
        interaction_date: form.interaction_date
          ? new Date(form.interaction_date + 'T00:00:00').toISOString()
          : undefined,
        follow_up_date: form.follow_up_required && form.follow_up_date
          ? new Date(form.follow_up_date + 'T00:00:00').toISOString()
          : undefined,
      }
      if (!body.sentiment)          delete body.sentiment
      if (!body.outcome)            delete body.outcome
      if (!body.product_discussed)  delete body.product_discussed
      if (!form.follow_up_required) delete body.follow_up_date

      const res = await fetch('/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => null)
        throw new Error(err?.detail || `Server error ${res.status}`)
      }
      setStatus('success')
      setForm(EMPTY_FORM())
      setTimeout(() => setStatus('idle'), 3000)
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Failed to save. Please try again.')
      setStatus('error')
      setTimeout(() => setStatus('idle'), 4000)
    }
  }, [form])

  // ── Chat send ────────────────────────────────────────────────────────────
  const handleChatSend = useCallback(() => {
    const text = chatInput.trim()
    if (!text || !isConnected || loading) return
    onChatSend(text)
    setChatInput('')
  }, [chatInput, isConnected, loading, onChatSend])

  return (
    <div className="flex flex-col h-full">

      {/* ── Tab bar ── */}
      <div className="flex-none flex border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        {([['chat', MessageSquare, 'Chat Mode'], ['form', FileText, 'Form Mode']] as const).map(
          ([id, Icon, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
                tab === id
                  ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                  : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          )
        )}
      </div>

      {/* ── Chat tab ── */}
      {tab === 'chat' && (
        <div className="flex-1 flex flex-col p-4 gap-3 overflow-y-auto">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Describe the interaction in plain language. The AI extracts HCP name, summary, sentiment, and follow-up automatically.
          </p>

          <div className="flex flex-col gap-2">
            {CHAT_EXAMPLES.map(ex => (
              <button
                key={ex}
                onClick={() => setChatInput(ex)}
                className="text-left text-xs px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-brand-400 hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
              >
                💬 {ex}
              </button>
            ))}
          </div>

          <div className="mt-auto flex gap-2 items-end">
            <textarea
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleChatSend())}
              placeholder="Met Dr. Sharma today, discussed Lipitor, follow up next week..."
              rows={3}
              disabled={!isConnected || loading}
              className="flex-1 px-4 py-3 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none disabled:opacity-50 text-slate-800 dark:text-slate-100 placeholder-slate-400"
            />
            <button
              onClick={handleChatSend}
              disabled={!chatInput.trim() || !isConnected || loading}
              className="p-3 rounded-xl bg-gradient-to-br from-brand-500 to-purple-600 text-white disabled:opacity-40 hover:shadow-md active:scale-95 transition-all"
            >
              {loading
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <Send className="w-4 h-4" />
              }
            </button>
          </div>
        </div>
      )}

      {/* ── Form tab ── */}
      {tab === 'form' && (
        <div className="flex-1 overflow-y-auto p-4 scrollbar-thin">
          <div className="flex flex-col gap-4 max-w-lg mx-auto">

            {status === 'success' && (
              <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 text-sm">
                <CheckCircle className="w-4 h-4 flex-none" /> Interaction logged successfully.
              </div>
            )}
            {status === 'error' && (
              <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm">
                <AlertCircle className="w-4 h-4 flex-none" /> {errorMsg || 'Failed to save. Please try again.'}
              </div>
            )}

            {/* HCP Name */}
            <Field label="HCP Name" required>
              <input value={form.hcp_name} onChange={e => set('hcp_name', e.target.value)}
                placeholder="Dr. Sharma" className={input} />
            </Field>

            {/* Date + Type */}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Date">
                <input type="date" value={form.interaction_date}
                  onChange={e => set('interaction_date', e.target.value)} className={input} />
              </Field>
              <Field label="Type">
                <select value={form.interaction_type}
                  onChange={e => set('interaction_type', e.target.value)} className={input}>
                  {INTERACTION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </Field>
            </div>

            {/* Notes */}
            <Field label="Notes" required>
              <textarea value={form.notes} onChange={e => set('notes', e.target.value)}
                placeholder="Discussed new drug trial, showed interest..." rows={3}
                className={`${input} resize-none`} />
            </Field>

            {/* Product + Sentiment */}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Product Discussed">
                <input value={form.product_discussed}
                  onChange={e => set('product_discussed', e.target.value)}
                  placeholder="Lipitor" className={input} />
              </Field>
              <Field label="Sentiment">
                <select value={form.sentiment} onChange={e => set('sentiment', e.target.value)} className={input}>
                  <option value="">— select —</option>
                  {SENTIMENTS.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </Field>
            </div>

            {/* Outcome */}
            <Field label="Outcome">
              <select value={form.outcome} onChange={e => set('outcome', e.target.value)} className={input}>
                <option value="">— select —</option>
                {OUTCOMES.map(o => <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>)}
              </select>
            </Field>

            {/* Follow-up toggle */}
            <div className="flex items-center gap-3">
              <button type="button" onClick={() => set('follow_up_required', !form.follow_up_required)}
                className={`relative w-10 h-5 rounded-full transition-colors ${
                  form.follow_up_required ? 'bg-brand-500' : 'bg-slate-300 dark:bg-slate-600'
                }`}>
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                  form.follow_up_required ? 'translate-x-5' : ''
                }`} />
              </button>
              <span className="text-sm text-slate-700 dark:text-slate-300">Follow-up required</span>
            </div>

            {form.follow_up_required && (
              <Field label="Follow-up Date">
                <input type="date" value={form.follow_up_date}
                  onChange={e => set('follow_up_date', e.target.value)} className={input} />
              </Field>
            )}

            {/* Submit */}
            <button
              onClick={handleFormSubmit}
              disabled={!form.hcp_name.trim() || !form.notes.trim() || status === 'saving'}
              className="flex items-center justify-center gap-2 w-full py-3 rounded-xl bg-gradient-to-r from-brand-500 to-purple-600 text-white font-medium text-sm disabled:opacity-40 hover:shadow-md active:scale-[0.98] transition-all"
            >
              {status === 'saving'
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Saving...</>
                : <><Save className="w-4 h-4" /> Log Interaction</>
              }
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────
const input = 'w-full px-4 py-2.5 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-500 text-slate-800 dark:text-slate-100 placeholder-slate-400'

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      {children}
    </div>
  )
}
