'use client'
import { useEffect, useState } from 'react'
import { useProducts, Product } from '@/lib/product-context'
import { apiFetch } from '@/lib/api'
import { createClient } from '@/lib/supabase-client'
import { PLATFORM_COLORS } from '@/lib/constants'

type TwitterStatus = {
  connected: boolean
  handle?: string
  connected_at?: string
  error?: string
}

export default function SettingsPage() {
  const { selectedProduct, selectedProductId, refreshProducts, loading: productsLoading } = useProducts()
  const [email, setEmail] = useState<string | null>(null)
  const [userId, setUserId] = useState<string | null>(null)
  const [twitterStatus, setTwitterStatus] = useState<TwitterStatus | null>(null)
  const [loadingTwitter, setLoadingTwitter] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)

  // Product editing state
  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editSystemPrompt, setEditSystemPrompt] = useState('')
  const [editKeywords, setEditKeywords] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const supabase = createClient()

  useEffect(() => {
    async function init() {
      const { data: { user } } = await supabase.auth.getUser()
      if (user) {
        setEmail(user.email || null)
        setUserId(user.id)
      }
    }
    init()
  }, [])

  useEffect(() => {
    if (selectedProductId) {
      checkTwitterStatus()
      resetEditState()
    }
  }, [selectedProductId])

  async function checkTwitterStatus() {
    if (!selectedProductId) return
    setLoadingTwitter(true)
    try {
      const data = await apiFetch<TwitterStatus>(`/settings/twitter-status?product_id=${selectedProductId}`)
      setTwitterStatus(data)
    } catch (e) {
      setTwitterStatus({ connected: false })
    } finally {
      setLoadingTwitter(false)
    }
  }

  async function disconnectTwitter() {
    if (!selectedProductId) return
    setDisconnecting(true)
    try {
      await apiFetch(`/settings/twitter-disconnect?product_id=${selectedProductId}`, { method: 'DELETE' })
      setTwitterStatus({ connected: false })
    } catch (e) {
      console.error('Failed to disconnect:', e)
    } finally {
      setDisconnecting(false)
    }
  }

  function resetEditState() {
    if (selectedProduct) {
      setEditName(selectedProduct.name || '')
      setEditDescription(selectedProduct.description || '')
      setEditSystemPrompt(selectedProduct.system_prompt || '')
      // Convert keyword arrays to newline-separated strings for textarea
      const kw: Record<string, string> = {}
      for (const [platform, keywords] of Object.entries(selectedProduct.keywords || {})) {
        kw[platform] = (keywords || []).join('\n')
      }
      setEditKeywords(kw)
    }
    setEditing(false)
    setSaveError(null)
  }

  async function saveProductSettings() {
    if (!selectedProductId) return
    setSaving(true)
    setSaveError(null)
    try {
      // Convert newline-separated keywords back to arrays
      const keywords: Record<string, string[]> = {}
      for (const [platform, text] of Object.entries(editKeywords)) {
        keywords[platform] = text.split('\n').map(k => k.trim()).filter(Boolean)
      }

      await apiFetch(`/products/${selectedProductId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: editName,
          description: editDescription,
          system_prompt: editSystemPrompt,
          keywords,
        }),
      })
      await refreshProducts()
      setEditing(false)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  if (productsLoading) {
    return <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'200px',color:'#999',fontSize:'14px'}}>Loading...</div>
  }

  if (!selectedProduct) {
    return (
      <div style={{textAlign:'center',padding:'80px 40px',background:'#fafafa',borderRadius:'16px',border:'1px solid #e8e8e8'}}>
        <div style={{fontSize:'32px',marginBottom:'12px'}}>&#9881;</div>
        <p style={{fontSize:'15px',fontWeight:500,color:'#111'}}>Select a product</p>
        <p style={{fontSize:'13px',color:'#999',marginTop:'4px'}}>Choose a product from the sidebar to view its settings</p>
      </div>
    )
  }

  return (
    <div style={{maxWidth:'700px'}}>
      <h1 style={{fontSize:'28px',fontWeight:600,color:'#111',marginBottom:'8px'}}>Settings</h1>
      <p style={{fontSize:'14px',color:'#999',marginBottom:'32px'}}>{selectedProduct.name} — Manage product settings and connections</p>

      {/* Account Section */}
      <div style={{marginBottom:'32px'}}>
        <h2 style={{fontSize:'16px',fontWeight:600,color:'#111',marginBottom:'16px'}}>Account</h2>
        <div style={{padding:'16px 20px',background:'#fafafa',borderRadius:'12px',border:'1px solid #e8e8e8'}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
            <div>
              <div style={{fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'4px'}}>Email</div>
              <div style={{fontSize:'14px',color:'#111'}}>{email || 'Not signed in'}</div>
            </div>
            {userId && (
              <div style={{textAlign:'right'}}>
                <div style={{fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'4px'}}>User ID</div>
                <div style={{fontSize:'11px',color:'#666',fontFamily:'monospace'}}>{userId.slice(0, 8)}...</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Twitter Connection Section */}
      <div style={{marginBottom:'32px'}}>
        <h2 style={{fontSize:'16px',fontWeight:600,color:'#111',marginBottom:'16px'}}>Twitter Connection</h2>
        <div style={{padding:'20px',background:'#fff',borderRadius:'12px',border:'1px solid #e8e8e8'}}>
          {loadingTwitter ? (
            <div style={{color:'#999',fontSize:'14px'}}>Checking connection...</div>
          ) : twitterStatus?.connected ? (
            <>
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:'12px'}}>
                <div style={{display:'flex',alignItems:'center',gap:'8px'}}>
                  <div style={{width:'8px',height:'8px',borderRadius:'50%',background:'#22c55e'}}/>
                  <span style={{fontSize:'14px',fontWeight:500,color:'#111'}}>Connected</span>
                  {twitterStatus.handle && (
                    <span style={{fontSize:'13px',color:'#666'}}>@{twitterStatus.handle}</span>
                  )}
                </div>
                <button
                  onClick={disconnectTwitter}
                  disabled={disconnecting}
                  style={{padding:'6px 12px',borderRadius:'6px',background:'#fff',border:'1px solid #e53935',color:'#e53935',fontSize:'12px',fontWeight:500,cursor:'pointer',opacity:disconnecting?0.5:1}}
                >
                  {disconnecting ? 'Disconnecting...' : 'Disconnect'}
                </button>
              </div>
              {twitterStatus.connected_at && (
                <div style={{fontSize:'12px',color:'#999'}}>
                  Connected {new Date(twitterStatus.connected_at).toLocaleDateString()}
                </div>
              )}
            </>
          ) : (
            <>
              <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'12px'}}>
                <div style={{width:'8px',height:'8px',borderRadius:'50%',background:'#999'}}/>
                <span style={{fontSize:'14px',fontWeight:500,color:'#111'}}>Not connected</span>
              </div>
              <div style={{padding:'16px',background:'#f8f9fa',borderRadius:'8px',marginBottom:'12px'}}>
                <div style={{fontSize:'13px',fontWeight:600,color:'#111',marginBottom:'8px'}}>Connect via Chrome Extension</div>
                <ol style={{fontSize:'13px',color:'#666',lineHeight:1.6,margin:0,paddingLeft:'20px'}}>
                  <li>Install the Operative1 Chrome extension</li>
                  <li>Log in to Twitter/X in your browser</li>
                  <li>Click the extension icon</li>
                  <li>Select this product and click "Connect"</li>
                </ol>
              </div>
              <div style={{fontSize:'12px',color:'#999'}}>
                Product ID: <code style={{background:'#f0f0f0',padding:'2px 6px',borderRadius:'4px',fontFamily:'monospace'}}>{selectedProductId}</code>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Product Settings Section */}
      <div style={{marginBottom:'32px'}}>
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:'16px'}}>
          <h2 style={{fontSize:'16px',fontWeight:600,color:'#111'}}>Product Settings</h2>
          {!editing && (
            <button
              onClick={() => { resetEditState(); setEditing(true) }}
              style={{padding:'6px 14px',borderRadius:'6px',background:'#111',color:'#fff',fontSize:'12px',fontWeight:500,border:'none',cursor:'pointer'}}
            >
              Edit
            </button>
          )}
        </div>

        <div style={{padding:'20px',background:'#fff',borderRadius:'12px',border:'1px solid #e8e8e8'}}>
          {editing ? (
            <div style={{display:'flex',flexDirection:'column',gap:'20px'}}>
              {/* Name */}
              <div>
                <label style={{display:'block',fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'6px'}}>Name</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  maxLength={100}
                  style={{width:'100%',padding:'10px 12px',borderRadius:'8px',border:'1px solid #e0e0e0',fontSize:'14px',outline:'none'}}
                />
              </div>

              {/* Description */}
              <div>
                <label style={{display:'block',fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'6px'}}>Description</label>
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={3}
                  style={{width:'100%',padding:'10px 12px',borderRadius:'8px',border:'1px solid #e0e0e0',fontSize:'14px',outline:'none',resize:'vertical',fontFamily:'inherit'}}
                />
              </div>

              {/* System Prompt */}
              <div>
                <label style={{display:'block',fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'6px'}}>System Prompt</label>
                <textarea
                  value={editSystemPrompt}
                  onChange={(e) => setEditSystemPrompt(e.target.value)}
                  rows={4}
                  maxLength={2000}
                  placeholder="Instructions for the AI when generating replies..."
                  style={{width:'100%',padding:'10px 12px',borderRadius:'8px',border:'1px solid #e0e0e0',fontSize:'14px',outline:'none',resize:'vertical',fontFamily:'inherit'}}
                />
                <div style={{fontSize:'11px',color:'#999',marginTop:'4px'}}>{editSystemPrompt.length}/2000</div>
              </div>

              {/* Keywords by platform */}
              <div>
                <label style={{display:'block',fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'12px'}}>Keywords by Platform</label>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px'}}>
                  {['twitter', 'reddit', 'linkedin', 'hn'].map(platform => (
                    <div key={platform}>
                      <div style={{display:'flex',alignItems:'center',gap:'6px',marginBottom:'6px'}}>
                        <div style={{width:'8px',height:'8px',borderRadius:'50%',background:PLATFORM_COLORS[platform] || '#666'}}/>
                        <span style={{fontSize:'12px',fontWeight:500,color:'#333',textTransform:'capitalize'}}>{platform === 'hn' ? 'Hacker News' : platform}</span>
                      </div>
                      <textarea
                        value={editKeywords[platform] || ''}
                        onChange={(e) => setEditKeywords(prev => ({ ...prev, [platform]: e.target.value }))}
                        rows={4}
                        placeholder="One keyword per line"
                        style={{width:'100%',padding:'8px 10px',borderRadius:'6px',border:'1px solid #e0e0e0',fontSize:'12px',outline:'none',resize:'vertical',fontFamily:'inherit'}}
                      />
                    </div>
                  ))}
                </div>
              </div>

              {saveError && (
                <div style={{padding:'10px 14px',background:'#ffebee',borderRadius:'8px',fontSize:'13px',color:'#c62828'}}>{saveError}</div>
              )}

              <div style={{display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                <button
                  onClick={resetEditState}
                  style={{padding:'8px 16px',borderRadius:'8px',background:'#f5f5f5',color:'#666',fontSize:'13px',fontWeight:500,border:'none',cursor:'pointer'}}
                >
                  Cancel
                </button>
                <button
                  onClick={saveProductSettings}
                  disabled={saving}
                  style={{padding:'8px 16px',borderRadius:'8px',background:'#111',color:'#fff',fontSize:'13px',fontWeight:500,border:'none',cursor:'pointer',opacity:saving?0.5:1}}
                >
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          ) : (
            <div style={{display:'flex',flexDirection:'column',gap:'16px'}}>
              <div>
                <div style={{fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'4px'}}>Name</div>
                <div style={{fontSize:'14px',color:'#111'}}>{selectedProduct.name}</div>
              </div>
              <div>
                <div style={{fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'4px'}}>Description</div>
                <div style={{fontSize:'14px',color:'#111'}}>{selectedProduct.description || <span style={{color:'#999'}}>No description</span>}</div>
              </div>
              {selectedProduct.system_prompt && (
                <div>
                  <div style={{fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'4px'}}>System Prompt</div>
                  <div style={{fontSize:'13px',color:'#666',lineHeight:1.5,whiteSpace:'pre-wrap'}}>{selectedProduct.system_prompt}</div>
                </div>
              )}
              <div>
                <div style={{fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'8px'}}>Keywords</div>
                <div style={{display:'flex',flexWrap:'wrap',gap:'8px'}}>
                  {Object.entries(selectedProduct.keywords || {}).map(([platform, keywords]) => (
                    keywords && keywords.length > 0 && (
                      <div key={platform} style={{padding:'8px 12px',background:'#f8f9fa',borderRadius:'8px'}}>
                        <span style={{fontSize:'11px',fontWeight:600,textTransform:'uppercase',color:PLATFORM_COLORS[platform] || '#666'}}>{platform}</span>
                        <span style={{fontSize:'12px',color:'#666',marginLeft:'8px'}}>{keywords.length} keywords</span>
                      </div>
                    )
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Danger Zone */}
      <div>
        <h2 style={{fontSize:'16px',fontWeight:600,color:'#e53935',marginBottom:'16px'}}>Danger Zone</h2>
        <div style={{padding:'20px',background:'#fff',borderRadius:'12px',border:'1px solid #ffcdd2'}}>
          <div style={{fontSize:'14px',fontWeight:500,color:'#111',marginBottom:'4px'}}>Delete Product</div>
          <p style={{fontSize:'13px',color:'#666',marginBottom:'12px'}}>
            Permanently delete this product and all its data. This action cannot be undone.
          </p>
          <button
            onClick={() => alert('Delete functionality coming soon. Contact support to delete a product.')}
            style={{padding:'8px 14px',borderRadius:'6px',background:'#fff',border:'1px solid #e53935',color:'#e53935',fontSize:'12px',fontWeight:500,cursor:'pointer'}}
          >
            Delete Product
          </button>
        </div>
      </div>
    </div>
  )
}
