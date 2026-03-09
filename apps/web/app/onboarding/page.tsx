'use client'
import { useState, useRef, useEffect } from 'react'
import { createClient } from '@/lib/supabase-client'
import { useRouter } from 'next/navigation'

type Message = { role: 'assistant' | 'user', content: string }

export default function OnboardingPage() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: "Welcome to Operative1.\n\nLet's set up your first product. Tell me what it's called and what it does — just describe it naturally." }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [productConfig, setProductConfig] = useState<any>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const router = useRouter()
  const supabase = createClient()

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])

  async function sendMessage() {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    const history = [...messages, { role: 'user' as const, content: userMsg }]
    setMessages(history)
    setLoading(true)

    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 1000,
        system: `You are an onboarding assistant for Operative1. Gather product info conversationally (one question at a time): name, description, value prop, target audience, platforms (Twitter/Reddit/LinkedIn/HN), tone. After 3-4 exchanges respond ONLY with this JSON: {"ready":true,"config":{"name":"","slug":"","description":"","value_prop":"","system_prompt":"","keywords":{"twitter":[],"reddit":[],"hn":[],"linkedin":[]},"tone":"","target_subreddits":[]}}. Be warm and brief until then.`,
        messages: history.map(m => ({ role: m.role, content: m.content }))
      })
    })
    const data = await res.json()
    const content = data.content[0].text
    try {
      const parsed = JSON.parse(content)
      if (parsed.ready && parsed.config) {
        setProductConfig(parsed.config)
        setMessages(prev => [...prev, { role: 'assistant', content: `All set! I've configured **${parsed.config.name}** with relevant keywords and a brand voice tailored to your audience.\n\nReady to launch?` }])
        setDone(true); setLoading(false); return
      }
    } catch {}
    setMessages(prev => [...prev, { role: 'assistant', content: content }])
    setLoading(false)
  }

  async function launchProduct() {
    if (!productConfig) return
    setLoading(true)
    const { data: { user } } = await supabase.auth.getUser()
    const { error } = await supabase.from('products').insert({
      ...productConfig, user_id: user?.id,
      auto_post: { twitter: false, reddit: false, linkedin: false, hn: false },
      max_daily_replies: { twitter: 5, reddit: 3, linkedin: 3, hn: 1 },
      active: true
    })
    if (error) { setMessages(prev => [...prev, { role: 'assistant', content: `Something went wrong: ${error.message}` }]); setLoading(false); return }
    router.push('/queue')
  }

  return (
    <div className="min-h-screen flex flex-col" style={{background:'#f5f5f7'}}>
      <header className="bg-white border-b border-[#d1d1d6] px-8 py-4 flex items-center justify-between">
        <span className="text-[13px] font-semibold tracking-[0.15em] uppercase text-[#6e6e73]">Operative1</span>
        <span className="text-[13px] text-[#6e6e73]">Product Setup</span>
      </header>

      <div className="flex-1 overflow-auto py-8 px-4">
        <div className="max-w-[600px] mx-auto space-y-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[480px] px-5 py-4 rounded-2xl text-[15px] leading-relaxed whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'text-white rounded-br-sm'
                  : 'bg-white text-[#1d1d1f] rounded-bl-sm'
              }`} style={m.role === 'user' ? {background:'#1d1d1f', boxShadow:'none'} : {boxShadow:'0 1px 8px rgba(0,0,0,0.08)'}}>
                {m.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white px-5 py-4 rounded-2xl rounded-bl-sm" style={{boxShadow:'0 1px 8px rgba(0,0,0,0.08)'}}>
                <div className="flex gap-1.5 items-center h-5">
                  {[0,150,300].map(d => (
                    <div key={d} className="w-2 h-2 rounded-full bg-[#aeaeb2] animate-bounce" style={{animationDelay:`${d}ms`}} />
                  ))}
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="bg-white border-t border-[#d1d1d6] px-4 py-4">
        <div className="max-w-[600px] mx-auto">
          {done && productConfig ? (
            <div className="flex gap-3">
              <button onClick={launchProduct} disabled={loading} className="flex-1 py-3.5 rounded-xl text-[15px] font-semibold text-white transition-opacity disabled:opacity-50" style={{background:'#1d1d1f'}}>
                Launch {productConfig.name}
              </button>
              <button onClick={() => setDone(false)} className="px-6 py-3.5 rounded-xl text-[15px] font-medium text-[#1d1d1f] border border-[#d1d1d6] hover:bg-[#f5f5f7] transition-colors">
                Edit
              </button>
            </div>
          ) : (
            <div className="flex gap-3">
              <input
                type="text" value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendMessage()}
                placeholder="Describe your product…"
                className="flex-1 px-4 py-3.5 rounded-xl text-[15px] text-[#1d1d1f] outline-none border border-[#d1d1d6] focus:border-[#1d1d1f] transition-colors bg-white"
              />
              <button onClick={sendMessage} disabled={loading || !input.trim()} className="px-6 py-3.5 rounded-xl text-[15px] font-semibold text-white transition-opacity disabled:opacity-40" style={{background:'#1d1d1f'}}>
                Send
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
