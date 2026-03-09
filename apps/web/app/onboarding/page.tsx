'use client'
import { useState, useRef, useEffect } from 'react'
import { createClient } from '@/lib/supabase-client'
import { useRouter } from 'next/navigation'

type Message = { role: 'assistant' | 'user', content: string }

export default function OnboardingPage() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: "Welcome to Operative1.\n\nLet's set up your first product. Tell me what it's called and what it does — describe it naturally." }
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
    const userMsg = input.trim(); setInput('')
    const history = [...messages, { role: 'user' as const, content: userMsg }]
    setMessages(history); setLoading(true)

    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514', max_tokens: 1000,
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
        setMessages(prev => [...prev, { role: 'assistant', content: `All set. I've configured ${parsed.config.name} with tailored keywords and brand voice.\n\nReady to launch?` }])
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
      max_daily_replies: { twitter: 5, reddit: 3, linkedin: 3, hn: 1 }, active: true
    })
    if (error) { setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${error.message}` }]); setLoading(false); return }
    router.push('/queue')
  }

  return (
    <div style={{minHeight:'100vh',display:'flex',flexDirection:'column',background:'#fafafa'}}>
      <header style={{background:'#fff',borderBottom:'1px solid #e8e8e8',padding:'16px 32px',display:'flex',alignItems:'center',justifyContent:'space-between'}}>
        <span style={{fontSize:'11px',fontWeight:700,letterSpacing:'0.2em',textTransform:'uppercase',color:'#111'}}>Operative1</span>
        <span style={{fontSize:'13px',color:'#999'}}>Product Setup</span>
      </header>

      <div style={{flex:1,overflowY:'auto',padding:'32px 16px'}}>
        <div style={{maxWidth:'560px',margin:'0 auto',display:'flex',flexDirection:'column',gap:'16px'}}>
          {messages.map((m, i) => (
            <div key={i} style={{display:'flex',justifyContent: m.role==='user'?'flex-end':'flex-start'}}>
              <div style={{
                maxWidth:'460px',padding:'14px 18px',borderRadius:'16px',fontSize:'14px',lineHeight:'1.6',whiteSpace:'pre-wrap',
                background: m.role==='user' ? '#111' : '#fff',
                color: m.role==='user' ? '#fff' : '#111',
                borderBottomRightRadius: m.role==='user' ? '4px' : '16px',
                borderBottomLeftRadius: m.role==='user' ? '16px' : '4px',
                boxShadow: m.role==='assistant' ? '0 1px 6px rgba(0,0,0,0.07)' : 'none',
                border: m.role==='assistant' ? '1px solid #e8e8e8' : 'none'
              }}>
                {m.content}
              </div>
            </div>
          ))}
          {loading && (
            <div style={{display:'flex',justifyContent:'flex-start'}}>
              <div style={{background:'#fff',border:'1px solid #e8e8e8',borderRadius:'16px',borderBottomLeftRadius:'4px',padding:'14px 18px',boxShadow:'0 1px 6px rgba(0,0,0,0.07)'}}>
                <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                  {[0,1,2].map(i => (
                    <div key={i} style={{width:'7px',height:'7px',borderRadius:'50%',background:'#ccc',animation:'bounce 1s infinite',animationDelay:`${i*150}ms`}} />
                  ))}
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div style={{background:'#fff',borderTop:'1px solid #e8e8e8',padding:'16px'}}>
        <div style={{maxWidth:'560px',margin:'0 auto'}}>
          {done && productConfig ? (
            <div style={{display:'flex',gap:'10px'}}>
              <button onClick={launchProduct} disabled={loading}
                style={{flex:1,padding:'13px',borderRadius:'10px',background:'#111',color:'#fff',fontSize:'14px',fontWeight:600,border:'none',cursor:'pointer',opacity:loading?0.5:1}}>
                Launch {productConfig.name}
              </button>
              <button onClick={() => setDone(false)}
                style={{padding:'13px 20px',borderRadius:'10px',background:'#fff',color:'#111',fontSize:'14px',fontWeight:500,border:'1px solid #e0e0e0',cursor:'pointer'}}>
                Edit
              </button>
            </div>
          ) : (
            <div style={{display:'flex',gap:'10px'}}>
              <input type="text" value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendMessage()}
                placeholder="Describe your product…"
                style={{flex:1,padding:'12px 16px',borderRadius:'10px',border:'1px solid #e0e0e0',fontSize:'14px',color:'#111',outline:'none',background:'#fafafa'}}
                onFocus={e=>{e.target.style.borderColor='#111';e.target.style.background='#fff'}}
                onBlur={e=>{e.target.style.borderColor='#e0e0e0';e.target.style.background='#fafafa'}}
              />
              <button onClick={sendMessage} disabled={loading || !input.trim()}
                style={{padding:'12px 24px',borderRadius:'10px',background:'#111',color:'#fff',fontSize:'14px',fontWeight:600,border:'none',cursor:'pointer',opacity:(!input.trim()||loading)?0.4:1}}>
                Send
              </button>
            </div>
          )}
        </div>
      </div>
      <style>{`@keyframes bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-6px)}}`}</style>
    </div>
  )
}
