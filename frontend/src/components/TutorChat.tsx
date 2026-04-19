import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Send, ExternalLink, Lightbulb } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { agentsApi } from '../api/agents'
import toast from 'react-hot-toast'

interface Resource { title: string; url: string; type: string }
interface Message {
  role: 'user' | 'agent'
  content: string
  resources?: Resource[]
  hintLevel?: number
  hintCount?: number
}

interface Props { currentTopic: string | null }

export default function TutorChat({ currentTopic }: Props) {
  const { user } = useAuth()
  const [messages, setMessages] = useState<Message[]>([
    { role: 'agent', content: "Hi! I'm your Wozly tutor 🤖 I'll guide you with hints — never give you direct answers. Ask me anything about your current topic!" }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [hintCount, setHintCount] = useState(0)
  const [isStreaming, setIsStreaming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || !user || loading) return
    const topic = currentTopic || 'General'
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)

    // Use SSE streaming
    try {
      const token = localStorage.getItem('access_token') ?? ''
      const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

      // POST to stream endpoint with fetch
      const resp = await fetch(`${BASE}/agent/tutor/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          user_id: user.user_id,
          topic_id: topic,
          message: userMsg,
          history: messages.slice(-10).map(m => ({ role: m.role, content: m.content })),
        }),
      })

      if (!resp.ok) throw new Error('Tutor request failed')

      setIsStreaming(true)
      let agentMsg = ''
      let msgResources: Resource[] = []
      let newHintCount = hintCount

      // Add placeholder agent message for streaming
      setMessages(prev => [...prev, { role: 'agent', content: '', hintLevel: (hintCount % 4) + 1 }])

      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        const lines = chunk.split('\n').filter(l => l.startsWith('data:'))

        for (const line of lines) {
          const data = JSON.parse(line.replace('data: ', ''))
          if (data.type === 'token') {
            agentMsg += data.content
            setMessages(prev => {
              const updated = [...prev]
              updated[updated.length - 1] = { ...updated[updated.length - 1], content: agentMsg }
              return updated
            })
          } else if (data.type === 'done') {
            msgResources = data.resources ?? []
            newHintCount = data.hint_count
            setMessages(prev => {
              const updated = [...prev]
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: agentMsg,
                resources: msgResources,
                hintCount: newHintCount,
              }
              return updated
            })
            setHintCount(newHintCount)
          }
        }
      }
      
      // If the stream ended without sending any message, the server crashed during StreamingResponse
      if (!agentMsg.trim()) {
        // Remove the empty placeholder
        setMessages(prev => prev.slice(0, -1))
        throw new Error("Stream closed prematurely without content")
      }
      
    } catch {
      // Fallback to non-streaming
      try {
        const data = await agentsApi.tutorChat(
          user.user_id, topic, userMsg,
          messages.slice(-10).map(m => ({ role: m.role, content: m.content }))
        )
        setMessages(prev => [...prev, {
          role: 'agent',
          content: data.hint,
          resources: data.resources,
          hintLevel: data.hint_level,
          hintCount: data.hint_count,
        }])
        setHintCount(data.hint_count)
      } catch {
        // Graceful fallback — provide a helpful response even when API is down
        const fallbackHint = `Great question about "${topic}"! 🤔\n\nHere's a hint to get you started:\n\n1. **Think about the fundamentals** — What are the core building blocks of ${topic}?\n2. **Break it down** — Try to decompose your question into smaller parts.\n3. **Look at examples** — Check the resources in your module card for practical examples.\n\nI'm having a brief connection issue with my AI brain, but try rephrasing your question or check the linked resources! The key to mastering ${topic} is consistent practice.`
        setMessages(prev => [...prev, {
          role: 'agent',
          content: fallbackHint,
        }])
      }
    } finally {
      setLoading(false)
      setIsStreaming(false)
    }
  }

  const HINT_LABELS = ['', 'What do you know?', 'Analogy', 'Partial Example', 'Final Step']

  return (
    <div className="flex flex-col h-full bg-transparent text-white">
      {/* Header */}
      <div className="flex items-center gap-3 p-4 border-b border-white/5">
        <div className="w-8 h-8 rounded-xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
          <Brain className="w-4 h-4 text-indigo-400" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-slate-200">Wozly Tutor</h3>
          {currentTopic && <p className="text-xs text-slate-500">Topic: {currentTopic}</p>}
        </div>
        {hintCount > 0 && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/20">
            <Lightbulb className="w-3 h-3 text-amber-400" />
            <span className="text-xs text-amber-400 font-medium">{hintCount} hints</span>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <AnimatePresence initial={false}>
          {messages.map((msg, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
              className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start gap-2'}>

              {msg.role === 'agent' && (
                <div className="w-6 h-6 rounded-full bg-indigo-500/20 border border-indigo-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                  <Brain className="w-3 h-3 text-indigo-400" />
                </div>
              )}

              <div className="max-w-[85%] lg:max-w-[75%] space-y-2">
                {msg.hintLevel && (
                  <div className="chip-active text-xs mb-1">
                    Hint {msg.hintLevel}/4 · {HINT_LABELS[msg.hintLevel]}
                  </div>
                )}
                <div className={msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-agent'}>
                  <p className="text-sm text-slate-200 whitespace-pre-wrap leading-relaxed break-words break-all">
                    {msg.content}
                    {isStreaming && i === messages.length - 1 && (
                      <motion.span animate={{ opacity: [1, 0] }} transition={{ duration: 0.6, repeat: Infinity }}
                        className="inline-block w-0.5 h-3.5 bg-indigo-400 ml-0.5 align-middle" />
                    )}
                  </p>
                </div>

                {/* Resource cards */}
                {msg.resources?.length > 0 && (
                  <div className="space-y-1.5">
                    {msg.resources.map((r, ri) => (
                      <a key={ri} href={r.url} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-2 glass px-2.5 py-1.5 rounded-lg hover:border-indigo-500/30 transition-colors group text-xs">
                        <span className="text-indigo-400 font-medium uppercase">{(typeof r?.type === 'string' ? r.type : 'LNK').slice(0,3)}</span>
                        <span className="text-slate-300 group-hover:text-white truncate">{typeof r?.title === 'string' ? r.title : 'Resource'}</span>
                        <ExternalLink className="w-3 h-3 text-slate-600 group-hover:text-slate-400" />
                      </a>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          ))}

          {loading && !isStreaming && (
            <div className="flex justify-start gap-2">
              <div className="w-6 h-6 rounded-full bg-indigo-500/20 flex items-center justify-center">
                <Brain className="w-3 h-3 text-indigo-400" />
              </div>
              <div className="chat-bubble-agent">
                <div className="flex gap-1">
                  {[0, 0.15, 0.3].map((d, i) => (
                    <motion.div key={i} className="w-1.5 h-1.5 bg-indigo-400 rounded-full"
                      animate={{ y: [0, -4, 0] }} transition={{ duration: 0.5, delay: d, repeat: Infinity }} />
                  ))}
                </div>
              </div>
            </div>
          )}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-white/5 flex gap-2">
        <input ref={inputRef} id="tutor-input" type="text"
          placeholder={currentTopic ? `Ask about ${currentTopic}...` : 'Ask your tutor...'}
          className="input-field flex-1 text-sm"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendMessage()} />
        <motion.button id="tutor-send" onClick={sendMessage} disabled={!input.trim() || loading}
          whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
          className="w-10 h-10 rounded-xl bg-indigo-500 flex items-center justify-center text-white disabled:opacity-30 flex-shrink-0">
          <Send className="w-4 h-4" />
        </motion.button>
      </div>
    </div>
  )
}
