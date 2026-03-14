'use client'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase-client'
import { ProductProvider, useProducts } from '@/lib/product-context'
import { apiFetch } from '@/lib/api'
import { useIsMobile } from '@/lib/hooks'

const nav = [
  { href: '/products', label: 'Products' },
  { href: '/queue', label: 'Queue' },
  { href: '/broadcast', label: 'Broadcast' },
  { href: '/history', label: 'History' },
  { href: '/analytics', label: 'Analytics' },
  { href: '/settings', label: 'Settings' },
]

// Bottom tab bar items (subset — Settings lives in hamburger)
const bottomTabs = [
  { href: '/queue', label: 'Queue' },
  { href: '/broadcast', label: 'Broadcast' },
  { href: '/products', label: 'Products' },
  { href: '/history', label: 'History' },
  { href: '/analytics', label: 'Analytics' },
]

function ProductSwitcher({ onSelect }: { onSelect?: () => void }) {
  const { products, selectedProduct, selectProduct, loading } = useProducts()
  const [open, setOpen] = useState(false)
  const { isMobile } = useIsMobile()

  if (loading || products.length <= 1) return null

  return (
    <div style={{ padding: '0 12px 12px', position: 'relative' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%',
          padding: isMobile ? '12px 14px' : '10px 12px',
          borderRadius: '8px',
          background: '#fff',
          border: '1px solid #e8e8e8',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: isMobile ? '15px' : '13px',
          fontWeight: 500,
          color: '#111',
          boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
          minHeight: '44px',
        }}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {selectedProduct?.name || 'Select product'}
        </span>
        <span style={{ fontSize: '10px', color: '#999', marginLeft: '8px' }}>{open ? '▲' : '▼'}</span>
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
            maxHeight: '300px',
            overflowY: 'auto',
          }}
        >
          {products.map((p) => (
            <button
              key={p.id}
              onClick={() => {
                selectProduct(p.id)
                setOpen(false)
                onSelect?.()
              }}
              style={{
                width: '100%',
                padding: isMobile ? '14px 14px' : '10px 12px',
                background: p.id === selectedProduct?.id ? '#f5f5f5' : 'transparent',
                border: 'none',
                borderBottom: '1px solid #f0f0f0',
                cursor: 'pointer',
                textAlign: 'left',
                fontSize: isMobile ? '15px' : '13px',
                color: '#111',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                minHeight: '44px',
              }}
            >
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: p.active ? '#22c55e' : '#999',
                  flexShrink: 0,
                }}
              />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                {p.name}
              </span>
              {p.pending_count ? (
                <span style={{ marginLeft: 'auto', fontSize: '12px', color: '#999', flexShrink: 0 }}>
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
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { isMobile } = useIsMobile()

  useEffect(() => {
    async function check() {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) { router.push('/login'); return }

      try {
        const { has_products } = await apiFetch<{has_products: boolean}>(`/products/check?user_id=${session.user.id}`)
        if (!has_products) { router.push('/onboarding'); return }
      } catch {
        router.push('/onboarding'); return
      }
      setAuthed(true)
    }
    check()
  }, [])

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setSidebarOpen(false)
  }, [pathname])

  async function signOut() {
    await supabase.auth.signOut()
    router.push('/login')
  }

  if (!authed) return null

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#fff', position: 'relative' }}>
      {/* Mobile: Hamburger header bar */}
      {isMobile && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, zIndex: 150,
          height: '52px', background: '#fafafa', borderBottom: '1px solid #e8e8e8',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 16px',
        }}>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              padding: '8px', fontSize: '20px', color: '#111',
              minWidth: '44px', minHeight: '44px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            aria-label="Menu"
          >
            {sidebarOpen ? '\u2715' : '\u2630'}
          </button>
          <span style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '0.15em', textTransform: 'uppercase', color: '#111' }}>
            Operative1
          </span>
          <div style={{ width: '44px' }} />
        </div>
      )}

      {/* Mobile: Sidebar overlay backdrop */}
      {isMobile && sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 190,
            background: 'rgba(0,0,0,0.4)',
            transition: 'opacity 0.2s',
          }}
        />
      )}

      {/* Sidebar */}
      <aside style={{
        width: isMobile ? '280px' : '220px',
        background: '#fafafa',
        borderRight: '1px solid #e8e8e8',
        display: 'flex',
        flexDirection: 'column',
        ...(isMobile ? {
          position: 'fixed',
          top: 0,
          left: sidebarOpen ? 0 : '-280px',
          bottom: 0,
          zIndex: 200,
          transition: 'left 0.25s ease',
          boxShadow: sidebarOpen ? '4px 0 20px rgba(0,0,0,0.15)' : 'none',
          overflowY: 'auto',
        } : {}),
      }}>
        <div style={{ padding: isMobile ? '20px 20px 16px' : '24px 20px 16px' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#111' }}>Operative1</div>
        </div>
        <ProductSwitcher onSelect={() => setSidebarOpen(false)} />
        <AutopilotIndicator />
        <nav style={{ flex: 1, padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {nav.map(n => (
            <Link key={n.href} href={n.href} onClick={() => setSidebarOpen(false)} style={{
              display: 'flex',
              padding: isMobile ? '12px 14px' : '8px 12px',
              borderRadius: '8px',
              fontSize: isMobile ? '16px' : '14px',
              fontWeight: 500,
              textDecoration: 'none',
              transition: 'background 0.1s',
              background: pathname === n.href ? '#fff' : 'transparent',
              color: pathname === n.href ? '#111' : '#666',
              boxShadow: pathname === n.href ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
              minHeight: '44px',
              alignItems: 'center',
            }}>
              {n.label}
            </Link>
          ))}
        </nav>
        <div style={{ padding: '12px' }}>
          <button onClick={signOut} style={{
            width: '100%', textAlign: 'left',
            padding: isMobile ? '12px 14px' : '8px 12px',
            borderRadius: '8px', fontSize: isMobile ? '16px' : '14px',
            color: '#999', background: 'none', border: 'none', cursor: 'pointer',
            minHeight: '44px',
          }}>
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main style={{
        flex: 1,
        overflowY: 'auto',
        padding: isMobile ? '68px 16px 80px' : '40px',
        background: '#fff',
        width: '100%',
      }}>
        {children}
      </main>

      {/* Mobile: Bottom Tab Bar */}
      {isMobile && (
        <nav style={{
          position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 150,
          height: '64px',
          background: '#fff',
          borderTop: '1px solid #e8e8e8',
          display: 'flex',
          alignItems: 'stretch',
          paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        }}>
          {bottomTabs.map(tab => {
            const active = pathname === tab.href
            return (
              <Link
                key={tab.href}
                href={tab.href}
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  textDecoration: 'none',
                  gap: '2px',
                  minHeight: '44px',
                  color: active ? '#111' : '#999',
                  position: 'relative',
                }}
              >
                {active && (
                  <div style={{
                    position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)',
                    width: '24px', height: '3px', borderRadius: '0 0 3px 3px', background: '#111',
                  }} />
                )}
                <span style={{
                  fontSize: '11px',
                  fontWeight: active ? 700 : 500,
                  letterSpacing: '0.02em',
                  marginTop: '4px',
                }}>
                  {tab.label}
                </span>
              </Link>
            )
          })}
        </nav>
      )}
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
