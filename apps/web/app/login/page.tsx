'use client'
import { useState } from 'react'
import { createClient } from '@/lib/supabase-client'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const router = useRouter()
  const supabase = createClient()

  async function handleSubmit() {
    setLoading(true); setError('')
    if (mode === 'signup') {
      const { error } = await supabase.auth.signUp({ email, password })
      if (error) { setError(error.message); setLoading(false); return }
      router.push('/onboarding')
    } else {
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) { setError(error.message); setLoading(false); return }
      router.push('/queue')
    }
    setLoading(false)
  }

  return (
    <div style={{minHeight:'100vh',display:'flex',alignItems:'center',justifyContent:'center',background:'#fafafa',padding:'24px'}}>
      <div style={{width:'100%',maxWidth:'380px'}}>
        <div style={{textAlign:'center',marginBottom:'40px'}}>
          <div style={{fontSize:'11px',fontWeight:600,letterSpacing:'0.2em',textTransform:'uppercase',color:'#999',marginBottom:'12px'}}>Operative1</div>
          <h1 style={{fontSize:'26px',fontWeight:600,color:'#111',lineHeight:1.2}}>
            {mode === 'login' ? 'Welcome back' : 'Get started'}
          </h1>
        </div>

        <div style={{background:'#fff',borderRadius:'16px',padding:'32px',border:'1px solid #e8e8e8',boxShadow:'0 4px 24px rgba(0,0,0,0.06)'}}>
          <div style={{marginBottom:'16px'}}>
            <label style={{display:'block',fontSize:'13px',fontWeight:500,color:'#111',marginBottom:'6px'}}>Email</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="you@company.com"
              style={{width:'100%',padding:'12px 14px',borderRadius:'10px',border:'1px solid #e0e0e0',fontSize:'14px',color:'#111',background:'#fafafa',outline:'none',transition:'border-color 0.15s'}}
              onFocus={e=>{e.target.style.borderColor='#111';e.target.style.background='#fff'}}
              onBlur={e=>{e.target.style.borderColor='#e0e0e0';e.target.style.background='#fafafa'}}
            />
          </div>
          <div style={{marginBottom:'8px'}}>
            <label style={{display:'block',fontSize:'13px',fontWeight:500,color:'#111',marginBottom:'6px'}}>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSubmit()}
              placeholder="••••••••"
              style={{width:'100%',padding:'12px 14px',borderRadius:'10px',border:'1px solid #e0e0e0',fontSize:'14px',color:'#111',background:'#fafafa',outline:'none',transition:'border-color 0.15s'}}
              onFocus={e=>{e.target.style.borderColor='#111';e.target.style.background='#fff'}}
              onBlur={e=>{e.target.style.borderColor='#e0e0e0';e.target.style.background='#fafafa'}}
            />
          </div>

          {error && <div style={{marginTop:'12px',padding:'10px 14px',background:'#fff5f5',borderRadius:'8px',fontSize:'13px',color:'#e53e3e'}}>{error}</div>}

          <button onClick={handleSubmit} disabled={loading}
            style={{width:'100%',marginTop:'24px',padding:'13px',borderRadius:'10px',background:'#111',color:'#fff',fontSize:'14px',fontWeight:600,border:'none',cursor:'pointer',opacity:loading?0.5:1,transition:'opacity 0.15s'}}>
            {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>

          <p style={{textAlign:'center',fontSize:'13px',color:'#999',marginTop:'20px'}}>
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}
              style={{color:'#111',fontWeight:500,background:'none',border:'none',cursor:'pointer',textDecoration:'underline',fontSize:'13px'}}>
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
