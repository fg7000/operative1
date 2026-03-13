'use client'
import { useState, useRef, useEffect } from 'react'
import { createClient } from '@/lib/supabase-client'
import { useRouter } from 'next/navigation'

type Message = { role: 'assistant' | 'user', content: string }
type MentionStrategy = 'website' | 'handle' | 'mix'

// Extension ID - set via env var
const EXTENSION_ID = process.env.NEXT_PUBLIC_EXTENSION_ID || ''

export default function OnboardingPage() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: "Welcome to Operative1.\n\nLet's set up your first product. Tell me what it's called and what it does — describe it naturally." }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [productConfig, setProductConfig] = useState<any>(null)
  // Mention strategy step
  const [showMentionStep, setShowMentionStep] = useState(false)
  const [mentionStrategy, setMentionStrategy] = useState<MentionStrategy>('website')
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [twitterHandle, setTwitterHandle] = useState('')
  // Autopilot step
  const [showAutopilotStep, setShowAutopilotStep] = useState(false)
  const [autopilotEnabled, setAutopilotEnabled] = useState(true) // ON by default
  // Extension step
  const [showExtensionStep, setShowExtensionStep] = useState(false)
  const [extensionInstalled, setExtensionInstalled] = useState<boolean | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const router = useRouter()
  const supabase = createClient()

  // Check for extension
  useEffect(() => {
    checkExtension()
  }, [])

  async function checkExtension(): Promise<boolean> {
    if (!EXTENSION_ID || typeof chrome === 'undefined' || !chrome.runtime?.sendMessage) {
      setExtensionInstalled(false)
      return false
    }
    try {
      const response = await new Promise<{success: boolean}>((resolve) => {
        chrome.runtime.sendMessage(EXTENSION_ID, { action: 'ping' }, (resp) => {
          if (chrome.runtime.lastError || !resp) {
            resolve({ success: false })
          } else {
            resolve(resp)
          }
        })
      })
      setExtensionInstalled(response.success)
      return response.success
    } catch {
      setExtensionInstalled(false)
      return false
    }
  }

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])

  async function sendMessage() {
    if (!input.trim() || loading) return
    const userMsg = input.trim(); setInput('')
    const history = [...messages, { role: 'user' as const, content: userMsg }]
    setMessages(history); setLoading(true)

    const API = process.env.NEXT_PUBLIC_API_URL || 'https://keen-mindfulness-production-970b.up.railway.app'
    const res = await fetch(`${API}/onboarding/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        system: `You are an onboarding assistant for Operative1. Gather product info conversationally (one question at a time): name, description, value prop, target audience, platforms (Twitter/Reddit/LinkedIn/HN), tone. After 3-4 exchanges respond ONLY with this JSON: {"ready":true,"config":{"name":"","slug":"","description":"","value_prop":"","system_prompt":"","keywords":{"twitter":[],"reddit":[],"hn":[],"linkedin":[]},"tone":"","target_subreddits":[]}}. Be warm and brief until then.`,
        messages: history.map(m => ({ role: m.role, content: m.content }))
      })
    })
    const data = await res.json()
    const content = data.content[0].text
    try {
      // Strip markdown code fences then extract the JSON object from surrounding text
      let jsonContent = content
      if (jsonContent.includes('```')) {
        jsonContent = jsonContent.split('\n').filter((line: string) => !line.includes('```')).join('\n').trim()
      }
      const first = jsonContent.indexOf('{')
      const last = jsonContent.lastIndexOf('}')
      if (first === -1 || last === -1 || last <= first) throw new Error('no JSON')
      jsonContent = jsonContent.slice(first, last + 1)
      const parsed = JSON.parse(jsonContent)
      if (parsed.ready && parsed.config) {
        const config = parsed.config
        // Set config and show mention step
        setProductConfig(config)
        setShowMentionStep(true)
        // Build a friendly confirmation message
        const keywordCount = Object.values(config.keywords || {}).flat().length
        const tone = config.tone || 'professional'
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `Great! I've configured ${config.name} with ${keywordCount} keywords and a ${tone} tone.\n\nOne more thing — how should we link to your product in replies?`
        }])
        setLoading(false)
        return
      }
    } catch {}
    setMessages(prev => [...prev, { role: 'assistant', content: content }])
    setLoading(false)
  }

  function confirmMentionStrategy() {
    // Validate based on selected strategy
    if (mentionStrategy === 'website' && !websiteUrl.trim()) {
      alert('Please enter your website URL')
      return
    }
    if (mentionStrategy === 'handle' && !twitterHandle.trim()) {
      alert('Please enter your Twitter handle')
      return
    }
    if (mentionStrategy === 'mix' && (!websiteUrl.trim() || !twitterHandle.trim())) {
      alert('Please enter both your website URL and Twitter handle')
      return
    }

    // Add mention settings to config
    const updatedConfig = {
      ...productConfig,
      website_url: websiteUrl.trim(),
      twitter_handle: twitterHandle.trim().startsWith('@') ? twitterHandle.trim() : `@${twitterHandle.trim()}`,
      mention_strategy: mentionStrategy,
    }
    setProductConfig(updatedConfig)
    setShowMentionStep(false)
    setShowAutopilotStep(true)
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: `Perfect! Your product mentions will use ${mentionStrategy === 'website' ? 'your website link' : mentionStrategy === 'handle' ? 'your Twitter handle' : 'a mix of both'}.\n\nOne last thing — let's set up automatic posting.`
    }])
  }

  function confirmAutopilot() {
    // Add autopilot setting to config
    const updatedConfig = {
      ...productConfig,
      autopilot: {
        enabled: autopilotEnabled,
        min_relevance_score: 7,
        min_confidence: 0.8,
        require_no_product_mention: true,
        use_human_schedule: true,
      }
    }
    setProductConfig(updatedConfig)
    setShowAutopilotStep(false)
    setShowExtensionStep(true)
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: autopilotEnabled
        ? `Autopilot is ON. Now let's connect your Twitter account so replies can be posted from your browser.`
        : `Autopilot is OFF. Now let's connect your Twitter account so you can post approved replies.`
    }])
  }

  function skipExtensionStep() {
    setShowExtensionStep(false)
    setDone(true)
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: `No problem! You can connect Twitter later from Settings.\n\nReady to launch?`
    }])
  }

  function confirmExtensionStep() {
    setShowExtensionStep(false)
    setDone(true)
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: extensionInstalled
        ? `Great! Extension is connected. ${autopilotEnabled ? 'Keep your dashboard tab open for continuous posting.' : 'Head to Queue to approve and post replies.'}\n\nReady to launch?`
        : `You can install the extension anytime from Settings.\n\nReady to launch?`
    }])
  }

  async function launchProduct() {
    if (!productConfig) return
    setLoading(true)

    // Check session is valid before creating product
    const { data: { user }, error: authError } = await supabase.auth.getUser()
    if (authError || !user?.id) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Your session has expired. Please sign out and sign in again to continue.`
      }])
      setLoading(false)
      return
    }

    const API = process.env.NEXT_PUBLIC_API_URL || 'https://keen-mindfulness-production-970b.up.railway.app'
    const res = await fetch(`${API}/products/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config: productConfig, user_id: user.id })
    })
    if (!res.ok) {
      const err = await res.text()
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err}` }])
      setLoading(false)
      return
    }
    router.push('/queue')
  }

  return (
    <div style={{minHeight:'100vh',display:'flex',flexDirection:'column',background:'#fafafa'}}>
      <header style={{background:'#fff',borderBottom:'1px solid #e8e8e8',padding:'16px 32px',display:'flex',alignItems:'center',justifyContent:'space-between'}}>
        <span style={{fontSize:'11px',fontWeight:700,letterSpacing:'0.2em',textTransform:'uppercase',color:'#111'}}>Operative1</span>
        <div style={{display:'flex',alignItems:'center',gap:'16px'}}>
          <span style={{fontSize:'13px',color:'#999'}}>Product Setup</span>
          <button onClick={async () => { await supabase.auth.signOut(); router.push('/login') }}
            style={{fontSize:'13px',color:'#999',background:'none',border:'none',cursor:'pointer',textDecoration:'underline'}}>
            Sign Out
          </button>
        </div>
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
          {showMentionStep ? (
            <div style={{display:'flex',flexDirection:'column',gap:'16px'}}>
              {/* Strategy Selection */}
              <div style={{display:'flex',gap:'8px'}}>
                {[
                  { key: 'website', label: 'Website link', desc: 'Recommended' },
                  { key: 'handle', label: 'Twitter profile', desc: '' },
                  { key: 'mix', label: 'Mix of both', desc: '' },
                ].map(opt => (
                  <button key={opt.key}
                    onClick={() => setMentionStrategy(opt.key as MentionStrategy)}
                    style={{
                      flex:1,padding:'12px',borderRadius:'10px',fontSize:'13px',fontWeight:500,
                      border: mentionStrategy === opt.key ? '2px solid #111' : '1px solid #e0e0e0',
                      background: mentionStrategy === opt.key ? '#f5f5f5' : '#fff',
                      color:'#111',cursor:'pointer',textAlign:'center'
                    }}>
                    {opt.label}
                    {opt.desc && <span style={{display:'block',fontSize:'10px',color:'#666',marginTop:'2px'}}>{opt.desc}</span>}
                  </button>
                ))}
              </div>

              {/* Input fields based on strategy */}
              {(mentionStrategy === 'website' || mentionStrategy === 'mix') && (
                <div>
                  <label style={{display:'block',fontSize:'12px',color:'#666',marginBottom:'4px'}}>
                    Website URL <span style={{color:'#999'}}>(becomes a clickable link)</span>
                  </label>
                  <input type="text" value={websiteUrl} onChange={e => setWebsiteUrl(e.target.value)}
                    placeholder="e.g. burnchat.ai"
                    style={{width:'100%',padding:'10px 14px',borderRadius:'8px',border:'1px solid #e0e0e0',fontSize:'14px',outline:'none'}}
                  />
                </div>
              )}
              {(mentionStrategy === 'handle' || mentionStrategy === 'mix') && (
                <div>
                  <label style={{display:'block',fontSize:'12px',color:'#666',marginBottom:'4px'}}>
                    Twitter handle <span style={{color:'#999'}}>(links to your profile)</span>
                  </label>
                  <input type="text" value={twitterHandle} onChange={e => setTwitterHandle(e.target.value)}
                    placeholder="e.g. @BurnChatAI"
                    style={{width:'100%',padding:'10px 14px',borderRadius:'8px',border:'1px solid #e0e0e0',fontSize:'14px',outline:'none'}}
                  />
                </div>
              )}

              {/* Explanation */}
              <div style={{padding:'12px',background:'#f8f9fa',borderRadius:'8px',fontSize:'12px',color:'#666',lineHeight:1.5}}>
                {mentionStrategy === 'website' && "People tap your website link and go straight to your product."}
                {mentionStrategy === 'handle' && "Links to your Twitter profile. Good if your profile is optimized for conversions."}
                {mentionStrategy === 'mix' && "We'll randomly alternate. Mostly website links (70%), sometimes your Twitter handle (30%)."}
              </div>

              <button onClick={confirmMentionStrategy}
                style={{padding:'13px',borderRadius:'10px',background:'#111',color:'#fff',fontSize:'14px',fontWeight:600,border:'none',cursor:'pointer'}}>
                Continue
              </button>
            </div>
          ) : showAutopilotStep ? (
            <div style={{display:'flex',flexDirection:'column',gap:'16px'}}>
              {/* Autopilot Toggle */}
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'16px',background:'#f8f9fa',borderRadius:'12px',border:'1px solid #e8e8e8'}}>
                <div style={{display:'flex',alignItems:'center',gap:'12px'}}>
                  <div style={{width:'10px',height:'10px',borderRadius:'50%',background: autopilotEnabled ? '#22c55e' : '#999',boxShadow: autopilotEnabled ? '0 0 8px rgba(34,197,94,0.5)' : 'none'}}/>
                  <span style={{fontSize:'15px',fontWeight:600,color:'#111'}}>Autopilot: {autopilotEnabled ? 'ON' : 'OFF'}</span>
                </div>
                <button
                  onClick={() => setAutopilotEnabled(!autopilotEnabled)}
                  style={{padding:'6px 14px',borderRadius:'6px',fontSize:'12px',fontWeight:500,border:'1px solid #e0e0e0',background:'#fff',color:'#666',cursor:'pointer'}}
                >
                  {autopilotEnabled ? 'Turn Off' : 'Turn On'}
                </button>
              </div>

              {/* Explanation */}
              <div style={{padding:'14px',background:'#fff',borderRadius:'10px',border:'1px solid #e8e8e8'}}>
                <div style={{fontSize:'13px',color:'#111',lineHeight:1.6,marginBottom:'12px'}}>
                  {autopilotEnabled
                    ? "Operative1 will automatically find relevant conversations and post replies on your schedule. You can review everything in your queue anytime."
                    : "You'll review and approve each reply before posting. Replies will wait in your queue for manual approval."}
                </div>
                <div style={{display:'flex',flexDirection:'column',gap:'6px'}}>
                  {autopilotEnabled && (
                    <>
                      <div style={{display:'flex',alignItems:'center',gap:'8px',fontSize:'12px',color:'#666'}}>
                        <span style={{color:'#22c55e'}}>●</span> Keep your dashboard tab open for continuous posting
                      </div>
                      <div style={{display:'flex',alignItems:'center',gap:'8px',fontSize:'12px',color:'#666'}}>
                        <span style={{color:'#999'}}>●</span> Turn off anytime from Settings
                      </div>
                    </>
                  )}
                </div>
              </div>

              <button onClick={confirmAutopilot}
                style={{padding:'13px',borderRadius:'10px',background:'#111',color:'#fff',fontSize:'14px',fontWeight:600,border:'none',cursor:'pointer'}}>
                Continue
              </button>
            </div>
          ) : showExtensionStep ? (
            <div style={{display:'flex',flexDirection:'column',gap:'16px'}}>
              {/* Extension Card */}
              <div style={{padding:'20px',background:'#fff',borderRadius:'12px',border:'1px solid #e8e8e8'}}>
                {/* Extension Icon */}
                <div style={{display:'flex',alignItems:'center',gap:'16px',marginBottom:'16px'}}>
                  <div style={{
                    width:'48px',height:'48px',borderRadius:'10px',background:'#1a1a1a',
                    display:'flex',alignItems:'center',justifyContent:'center'
                  }}>
                    <span style={{fontSize:'16px',fontWeight:700,color:'#fff'}}>OP1</span>
                  </div>
                  <div>
                    <div style={{fontSize:'15px',fontWeight:600,color:'#111'}}>Operative1 Chrome Extension</div>
                    <div style={{fontSize:'13px',color:'#666'}}>Posts replies from your browser</div>
                  </div>
                </div>

                {extensionInstalled ? (
                  <div style={{padding:'12px',background:'#e8f5e9',borderRadius:'8px',display:'flex',alignItems:'center',gap:'10px',marginBottom:'16px'}}>
                    <span style={{width:'10px',height:'10px',borderRadius:'50%',background:'#4caf50'}}></span>
                    <span style={{fontSize:'14px',fontWeight:500,color:'#2e7d32'}}>Extension installed and ready!</span>
                  </div>
                ) : (
                  <>
                    <a
                      href="/extension"
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display:'flex',alignItems:'center',justifyContent:'center',gap:'8px',
                        width:'100%',padding:'12px',background:'#111',color:'#fff',
                        borderRadius:'8px',fontSize:'14px',fontWeight:600,
                        textDecoration:'none',marginBottom:'16px'
                      }}
                    >
                      Install Chrome Extension
                    </a>

                    {/* Steps */}
                    <div style={{display:'flex',flexDirection:'column',gap:'10px',marginBottom:'16px'}}>
                      {[
                        { num: '1', text: 'Install extension from Chrome Web Store' },
                        { num: '2', text: 'Make sure you\'re logged into Twitter/X' },
                        { num: '3', text: 'Click the extension icon in Chrome' },
                        { num: '4', text: 'Select your product and click Connect' },
                      ].map((step, i) => (
                        <div key={i} style={{display:'flex',alignItems:'center',gap:'12px'}}>
                          <div style={{
                            width:'24px',height:'24px',borderRadius:'50%',
                            background:'#f5f5f5',border:'1px solid #e0e0e0',
                            display:'flex',alignItems:'center',justifyContent:'center',
                            fontSize:'12px',fontWeight:600,color:'#666'
                          }}>{step.num}</div>
                          <span style={{fontSize:'13px',color:'#666'}}>{step.text}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}

                {/* Security info */}
                <div style={{padding:'12px',background:'#f8f9fa',borderRadius:'8px'}}>
                  <div style={{display:'flex',flexDirection:'column',gap:'6px'}}>
                    <div style={{fontSize:'12px',color:'#666',display:'flex',alignItems:'center',gap:'6px'}}>
                      <span style={{color:'#22c55e'}}>✓</span> Posts from YOUR browser using YOUR session
                    </div>
                    <div style={{fontSize:'12px',color:'#666',display:'flex',alignItems:'center',gap:'6px'}}>
                      <span style={{color:'#22c55e'}}>✓</span> Your credentials never leave your browser
                    </div>
                    <div style={{fontSize:'12px',color:'#666',display:'flex',alignItems:'center',gap:'6px'}}>
                      <span style={{color:'#22c55e'}}>✓</span> Disconnect anytime with one click
                    </div>
                  </div>
                </div>
              </div>

              <div style={{display:'flex',gap:'10px'}}>
                <button onClick={confirmExtensionStep}
                  style={{flex:1,padding:'13px',borderRadius:'10px',background:'#111',color:'#fff',fontSize:'14px',fontWeight:600,border:'none',cursor:'pointer'}}>
                  {extensionInstalled ? 'Continue' : 'I\'ll do this later'}
                </button>
                {!extensionInstalled && (
                  <button onClick={() => checkExtension()}
                    style={{padding:'13px 20px',borderRadius:'10px',background:'#fff',color:'#111',fontSize:'14px',fontWeight:500,border:'1px solid #e0e0e0',cursor:'pointer'}}>
                    Check Again
                  </button>
                )}
              </div>

              {!extensionInstalled && (
                <button onClick={skipExtensionStep}
                  style={{padding:'8px',background:'transparent',border:'none',color:'#999',fontSize:'13px',cursor:'pointer',textDecoration:'underline'}}>
                  Skip for now
                </button>
              )}
            </div>
          ) : done && productConfig ? (
            <div style={{display:'flex',gap:'10px'}}>
              <button onClick={launchProduct} disabled={loading}
                style={{flex:1,padding:'13px',borderRadius:'10px',background:'#111',color:'#fff',fontSize:'14px',fontWeight:600,border:'none',cursor:'pointer',opacity:loading?0.5:1}}>
                Launch {productConfig.name}
              </button>
              <button onClick={() => { setDone(false); setShowMentionStep(true) }}
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
