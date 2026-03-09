'use client'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase-client'

const nav = [
  { href: '/products', label: 'Products' },
  { href: '/queue', label: 'Queue' },
  { href: '/history', label: 'History' },
  { href: '/analytics', label: 'Analytics' },
  { href: '/settings', label: 'Settings' },
]

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const supabase = createClient()
  const [authed, setAuthed] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) router.push('/login')
      else setAuthed(true)
    })
  }, [])

  async function signOut() {
    await supabase.auth.signOut()
    router.push('/login')
  }

  if (!authed) return null

  return (
    <div style={{display:'flex',height:'100vh',background:'#fff'}}>
      <aside style={{width:'200px',background:'#fafafa',borderRight:'1px solid #e8e8e8',display:'flex',flexDirection:'column'}}>
        <div style={{padding:'24px 20px 16px'}}>
          <div style={{fontSize:'11px',fontWeight:700,letterSpacing:'0.2em',textTransform:'uppercase',color:'#111'}}>Operative1</div>
        </div>
        <nav style={{flex:1,padding:'8px 12px',display:'flex',flexDirection:'column',gap:'2px'}}>
          {nav.map(n => (
            <Link key={n.href} href={n.href} style={{
              display:'block',padding:'8px 12px',borderRadius:'8px',fontSize:'14px',fontWeight:500,textDecoration:'none',transition:'background 0.1s',
              background: pathname===n.href ? '#fff' : 'transparent',
              color: pathname===n.href ? '#111' : '#666',
              boxShadow: pathname===n.href ? '0 1px 4px rgba(0,0,0,0.08)' : 'none'
            }}>
              {n.label}
            </Link>
          ))}
        </nav>
        <div style={{padding:'12px'}}>
          <button onClick={signOut} style={{width:'100%',textAlign:'left',padding:'8px 12px',borderRadius:'8px',fontSize:'14px',color:'#999',background:'none',border:'none',cursor:'pointer'}}>
            Sign Out
          </button>
        </div>
      </aside>
      <main style={{flex:1,overflowY:'auto',padding:'40px',background:'#fff'}}>{children}</main>
    </div>
  )
}
