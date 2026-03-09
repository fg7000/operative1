'use client'
import { useState } from 'react'
import { createClient } from '@/lib/supabase-client'

export default function LoginPage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const supabase = createClient()

  async function handleGoogleLogin() {
    setLoading(true); setError('')
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: 'https://operative1.vercel.app/queue' }
    })
    if (error) { setError(error.message); setLoading(false) }
  }

  return (
    <div style={{minHeight:'100vh',display:'flex',alignItems:'center',justifyContent:'center',background:'#fafafa',padding:'24px'}}>
      <div style={{width:'100%',maxWidth:'380px'}}>
        <div style={{textAlign:'center',marginBottom:'40px'}}>
          <div style={{fontSize:'11px',fontWeight:600,letterSpacing:'0.2em',textTransform:'uppercase',color:'#999',marginBottom:'12px'}}>Operative1</div>
          <h1 style={{fontSize:'26px',fontWeight:600,color:'#111',lineHeight:1.2}}>Welcome</h1>
        </div>

        <div style={{background:'#fff',borderRadius:'16px',padding:'32px',border:'1px solid #e8e8e8',boxShadow:'0 4px 24px rgba(0,0,0,0.06)'}}>
          {error && <div style={{marginBottom:'16px',padding:'10px 14px',background:'#fff5f5',borderRadius:'8px',fontSize:'13px',color:'#e53e3e'}}>{error}</div>}

          <button onClick={handleGoogleLogin} disabled={loading}
            style={{width:'100%',padding:'13px',borderRadius:'10px',background:'#111',color:'#fff',fontSize:'14px',fontWeight:600,border:'none',cursor:'pointer',opacity:loading?0.5:1,transition:'opacity 0.15s',display:'flex',alignItems:'center',justifyContent:'center',gap:'10px'}}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A11.96 11.96 0 0 0 1 12c0 1.94.46 3.77 1.18 5.07l3.66-2.84v-.14z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            {loading ? 'Redirecting…' : 'Continue with Google'}
          </button>
        </div>
      </div>
    </div>
  )
}
