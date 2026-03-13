'use client'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase-client'
import { ProductProvider, useProducts } from '@/lib/product-context'
import { apiFetch } from '@/lib/api'

const nav = [
  { href: '/products', label: 'Products' },
  { href: '/queue', label: 'Queue' },
  { href: '/broadcast', label: 'Broadcast' },
  { href: '/history', label: 'History' },
  { href: '/analytics', label: 'Analytics' },
  { href: '/settings', label: 'Settings' },
]

function ProductSwitcher() {
  const { products, selectedProduct, selectProduct, loading } = useProducts()
  const [open, setOpen] = useState(false)

  if (loading || products.length <= 1) return null

  return (
    <div style={{ padding: '0 12px 12px', position: 'relative' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%',
          padding: '10px 12px',
          borderRadius: '8px',
          background: '#fff',
          border: '1px solid #e8e8e8',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '13px',
          fontWeight: 500,
          color: '#111',
          boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        }}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {selectedProduct?.name || 'Select product'}
        </span>
        <span style={{ fontSize: '10px', color: '#999', marginLeft: '8px' }}>▼</span>
      </button>
      {open && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: '12px',
            right: '12px',
            background: '#fff',
            border: '1px solid #e8e8e8',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 100,
            marginTop: '4px',
            maxHeight: '200px',
            overflowY: 'auto',
          }}
        >
          {products.map((p) => (
            <button
              key={p.id}
              onClick={() => {
                selectProduct(p.id)
                setOpen(false)
              }}
              style={{
                width: '100%',
                padding: '10px 12px',
                background: p.id === selectedProduct?.id ? '#f5f5f5' : 'transparent',
                border: 'none',
                borderBottom: '1px solid #f0f0f0',
                cursor: 'pointer',
                textAlign: 'left',
                fontSize: '13px',
                color: '#111',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: p.active ? '#22c55e' : '#999',
                }}
              />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {p.name}
              </span>
              {p.pending_count ? (
                <span style={{ marginLeft: 'auto', fontSize: '11px', color: '#999' }}>
                  {p.pending_count}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function AutopilotIndicator() {
  const { selectedProduct } = useProducts()
  const isAutopilotActive = selectedProduct?.autopilot?.enabled ?? false

  // Add beforeunload warning when autopilot is active
  useEffect(() => {
    if (!isAutopilotActive) return

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = 'Autopilot is running. Closing this tab will pause automatic posting.'
      return e.returnValue
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [isAutopilotActive])

  if (!isAutopilotActive) return null

  return (
    <div style={{
      padding: '8px 12px',
      margin: '0 12px 8px',
      background: 'rgba(34, 197, 94, 0.08)',
      borderRadius: '8px',
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
    }}>
      <div style={{
        width: '8px',
        height: '8px',
        borderRadius: '50%',
        background: '#22c55e',
        animation: 'autopilotPulse 2s ease-in-out infinite',
      }}/>
      <span style={{ fontSize: '12px', fontWeight: 500, color: '#166534' }}>Autopilot active</span>
    </div>
  )
}

function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const supabase = createClient()
  const [authed, setAuthed] = useState(false)

  useEffect(() => {
    async function check() {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) { router.push('/login'); return }

      try {
        const { has_products } = await apiFetch<{has_products: boolean}>(`/products/check?user_id=${session.user.id}`)
        if (!has_products) { router.push('/onboarding'); return }
      } catch {
        // If check fails, redirect to onboarding
        router.push('/onboarding'); return
      }
      setAuthed(true)
    }
    check()
  }, [])

  async function signOut() {
    await supabase.auth.signOut()
    router.push('/login')
  }

  if (!authed) return null

  return (
    <div style={{display:'flex',height:'100vh',background:'#fff'}}>
      <aside style={{width:'220px',background:'#fafafa',borderRight:'1px solid #e8e8e8',display:'flex',flexDirection:'column'}}>
        <div style={{padding:'24px 20px 16px'}}>
          <div style={{fontSize:'11px',fontWeight:700,letterSpacing:'0.2em',textTransform:'uppercase',color:'#111'}}>Operative1</div>
        </div>
        <ProductSwitcher />
        <AutopilotIndicator />
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

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProductProvider>
      <DashboardShell>{children}</DashboardShell>
      <style>{`
        @keyframes autopilotPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(1.2); }
        }
      `}</style>
    </ProductProvider>
  )
}
