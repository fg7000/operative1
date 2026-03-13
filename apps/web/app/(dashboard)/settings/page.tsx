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

type TargetingConfig = {
  max_tweet_age_hours: number
  min_likes: number
  min_author_followers: number
  max_reply_count: number
  min_opportunity_score: number
  max_ai_calls_per_run: number
}

type MentionStrategy = 'website' | 'handle' | 'mix'

type AutopilotConfig = {
  enabled: boolean
  min_relevance_score: number
  min_confidence: number
  require_no_product_mention: boolean
}

type PostingHoursConfig = {
  enabled: boolean
  timezone: string
  start_hour: number
  end_hour: number
  days_of_week: number[]
}

const TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Asia/Tokyo',
  'Asia/Singapore',
  'Australia/Sydney',
]

const DAYS_OF_WEEK = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

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

  // Fire rate control state
  const [editMaxDailyReplies, setEditMaxDailyReplies] = useState<Record<string, number>>({})
  const [editMaxHourlyReplies, setEditMaxHourlyReplies] = useState<Record<string, number>>({})
  const [editMinDelay, setEditMinDelay] = useState(120)

  // Posting hours state
  const [editPostingHours, setEditPostingHours] = useState<PostingHoursConfig>({
    enabled: false,
    timezone: 'UTC',
    start_hour: 9,
    end_hour: 21,
    days_of_week: [0, 1, 2, 3, 4],
  })

  // Autopilot state
  const [editAutopilot, setEditAutopilot] = useState<AutopilotConfig>({
    enabled: false,
    min_relevance_score: 7,
    min_confidence: 0.8,
    require_no_product_mention: true,
  })

  // Targeting state
  const [editTargeting, setEditTargeting] = useState<TargetingConfig>({
    max_tweet_age_hours: 24,
    min_likes: 2,
    min_author_followers: 50,
    max_reply_count: 100,
    min_opportunity_score: 10,
    max_ai_calls_per_run: 20,
  })

  // Mention strategy state
  const [editMentionStrategy, setEditMentionStrategy] = useState<MentionStrategy>('website')
  const [editWebsiteUrl, setEditWebsiteUrl] = useState('')
  const [editTwitterHandle, setEditTwitterHandle] = useState('')

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

      // Fire rate controls
      setEditMaxDailyReplies(selectedProduct.max_replies_per_day || { twitter: 10, reddit: 5, linkedin: 5, hn: 2 })
      setEditMaxHourlyReplies(selectedProduct.max_replies_per_hour || { twitter: 3, reddit: 2, linkedin: 2, hn: 1 })
      setEditMinDelay(selectedProduct.min_delay_between_posts || 120)

      // Posting hours
      setEditPostingHours(selectedProduct.posting_hours || {
        enabled: false,
        timezone: 'UTC',
        start_hour: 9,
        end_hour: 21,
        days_of_week: [0, 1, 2, 3, 4],
      })

      // Autopilot
      setEditAutopilot(selectedProduct.autopilot || {
        enabled: false,
        min_relevance_score: 7,
        min_confidence: 0.8,
        require_no_product_mention: true,
      })

      // Targeting
      setEditTargeting(selectedProduct.targeting || {
        max_tweet_age_hours: 24,
        min_likes: 2,
        min_author_followers: 50,
        max_reply_count: 100,
        min_opportunity_score: 10,
        max_ai_calls_per_run: 20,
      })

      // Mention strategy
      setEditMentionStrategy(selectedProduct.mention_strategy || 'website')
      setEditWebsiteUrl(selectedProduct.website_url || '')
      setEditTwitterHandle(selectedProduct.twitter_handle || '')
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
          // Fire rate controls
          max_replies_per_day: editMaxDailyReplies,
          max_replies_per_hour: editMaxHourlyReplies,
          min_delay_between_posts: editMinDelay,
          // Posting hours
          posting_hours: editPostingHours,
          // Autopilot
          autopilot: editAutopilot,
          // Targeting
          targeting: editTargeting,
          // Mention strategy
          website_url: editWebsiteUrl,
          twitter_handle: editTwitterHandle,
          mention_strategy: editMentionStrategy,
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

              {/* Product Mention Strategy */}
              <div style={{borderTop:'1px solid #e8e8e8',paddingTop:'20px'}}>
                <label style={{display:'block',fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'12px'}}>Product Mention in Replies</label>
                <p style={{fontSize:'12px',color:'#666',marginBottom:'12px'}}>
                  How should we link to your product when generating replies?
                </p>

                {/* Strategy Selection */}
                <div style={{display:'flex',gap:'8px',marginBottom:'16px'}}>
                  {[
                    { key: 'website', label: 'Website link', desc: 'Recommended' },
                    { key: 'handle', label: 'Twitter profile', desc: '' },
                    { key: 'mix', label: 'Mix of both', desc: '' },
                  ].map(opt => (
                    <button key={opt.key} type="button"
                      onClick={() => setEditMentionStrategy(opt.key as MentionStrategy)}
                      style={{
                        flex:1,padding:'10px',borderRadius:'8px',fontSize:'12px',fontWeight:500,
                        border: editMentionStrategy === opt.key ? '2px solid #111' : '1px solid #e0e0e0',
                        background: editMentionStrategy === opt.key ? '#f5f5f5' : '#fff',
                        color:'#111',cursor:'pointer',textAlign:'center'
                      }}>
                      {opt.label}
                      {opt.desc && <span style={{display:'block',fontSize:'10px',color:'#666',marginTop:'2px'}}>{opt.desc}</span>}
                    </button>
                  ))}
                </div>

                {/* Input fields */}
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'12px'}}>
                  <div>
                    <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>
                      Website URL {(editMentionStrategy === 'website' || editMentionStrategy === 'mix') && <span style={{color:'#e53935'}}>*</span>}
                    </label>
                    <input
                      type="text"
                      value={editWebsiteUrl}
                      onChange={(e) => setEditWebsiteUrl(e.target.value)}
                      placeholder="e.g. burnchat.ai"
                      style={{width:'100%',padding:'8px 10px',borderRadius:'6px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                    />
                    <div style={{fontSize:'10px',color:'#999',marginTop:'4px'}}>Becomes a clickable link</div>
                  </div>
                  <div>
                    <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>
                      Twitter Handle {(editMentionStrategy === 'handle' || editMentionStrategy === 'mix') && <span style={{color:'#e53935'}}>*</span>}
                    </label>
                    <input
                      type="text"
                      value={editTwitterHandle}
                      onChange={(e) => setEditTwitterHandle(e.target.value)}
                      placeholder="e.g. @BurnChatAI"
                      style={{width:'100%',padding:'8px 10px',borderRadius:'6px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                    />
                    <div style={{fontSize:'10px',color:'#999',marginTop:'4px'}}>Links to your profile</div>
                  </div>
                </div>

                {/* Explanation */}
                <div style={{padding:'10px',background:'#f8f9fa',borderRadius:'6px',fontSize:'11px',color:'#666',marginTop:'12px'}}>
                  {editMentionStrategy === 'website' && "Website: People tap and go straight to your product. Best for conversions."}
                  {editMentionStrategy === 'handle' && "Twitter: Links to your profile. Good if your profile is optimized for conversions."}
                  {editMentionStrategy === 'mix' && "Mix: Randomly alternate. Mostly website links (70%), sometimes your Twitter handle (30%)."}
                </div>
              </div>

              {/* Fire Rate Controls */}
              <div style={{borderTop:'1px solid #e8e8e8',paddingTop:'20px'}}>
                <label style={{display:'block',fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'12px'}}>Posting Limits</label>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px'}}>
                  {['twitter', 'reddit'].map(platform => (
                    <div key={platform} style={{padding:'12px',background:'#f8f9fa',borderRadius:'8px'}}>
                      <div style={{display:'flex',alignItems:'center',gap:'6px',marginBottom:'8px'}}>
                        <div style={{width:'8px',height:'8px',borderRadius:'50%',background:PLATFORM_COLORS[platform] || '#666'}}/>
                        <span style={{fontSize:'12px',fontWeight:500,color:'#333',textTransform:'capitalize'}}>{platform}</span>
                      </div>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                        <div>
                          <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>Max/Day</label>
                          <input
                            type="number"
                            min={1}
                            max={100}
                            value={editMaxDailyReplies[platform] || 10}
                            onChange={(e) => setEditMaxDailyReplies(prev => ({ ...prev, [platform]: parseInt(e.target.value) || 10 }))}
                            style={{width:'100%',padding:'6px 8px',borderRadius:'4px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                          />
                        </div>
                        <div>
                          <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>Max/Hour</label>
                          <input
                            type="number"
                            min={1}
                            max={20}
                            value={editMaxHourlyReplies[platform] || 3}
                            onChange={(e) => setEditMaxHourlyReplies(prev => ({ ...prev, [platform]: parseInt(e.target.value) || 3 }))}
                            style={{width:'100%',padding:'6px 8px',borderRadius:'4px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <div style={{marginTop:'12px'}}>
                  <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>Minimum seconds between posts</label>
                  <input
                    type="number"
                    min={30}
                    max={3600}
                    value={editMinDelay}
                    onChange={(e) => setEditMinDelay(parseInt(e.target.value) || 120)}
                    style={{width:'120px',padding:'6px 8px',borderRadius:'4px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                  />
                </div>
              </div>

              {/* Posting Hours */}
              <div style={{borderTop:'1px solid #e8e8e8',paddingTop:'20px'}}>
                <div style={{display:'flex',alignItems:'center',gap:'12px',marginBottom:'12px'}}>
                  <label style={{fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999'}}>Posting Hours</label>
                  <label style={{display:'flex',alignItems:'center',gap:'6px',cursor:'pointer'}}>
                    <input
                      type="checkbox"
                      checked={editPostingHours.enabled}
                      onChange={(e) => setEditPostingHours(prev => ({ ...prev, enabled: e.target.checked }))}
                    />
                    <span style={{fontSize:'12px',color:'#666'}}>Enable</span>
                  </label>
                </div>
                {editPostingHours.enabled && (
                  <div style={{padding:'12px',background:'#f8f9fa',borderRadius:'8px'}}>
                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'12px',marginBottom:'12px'}}>
                      <div>
                        <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>Timezone</label>
                        <select
                          value={editPostingHours.timezone}
                          onChange={(e) => setEditPostingHours(prev => ({ ...prev, timezone: e.target.value }))}
                          style={{width:'100%',padding:'6px 8px',borderRadius:'4px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                        >
                          {TIMEZONES.map(tz => <option key={tz} value={tz}>{tz}</option>)}
                        </select>
                      </div>
                      <div>
                        <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>Start Hour</label>
                        <input
                          type="number"
                          min={0}
                          max={23}
                          value={editPostingHours.start_hour}
                          onChange={(e) => setEditPostingHours(prev => ({ ...prev, start_hour: parseInt(e.target.value) || 9 }))}
                          style={{width:'100%',padding:'6px 8px',borderRadius:'4px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                        />
                      </div>
                      <div>
                        <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>End Hour</label>
                        <input
                          type="number"
                          min={0}
                          max={23}
                          value={editPostingHours.end_hour}
                          onChange={(e) => setEditPostingHours(prev => ({ ...prev, end_hour: parseInt(e.target.value) || 21 }))}
                          style={{width:'100%',padding:'6px 8px',borderRadius:'4px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                        />
                      </div>
                    </div>
                    <div>
                      <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>Days of Week</label>
                      <div style={{display:'flex',gap:'4px'}}>
                        {DAYS_OF_WEEK.map((day, idx) => (
                          <button
                            key={day}
                            type="button"
                            onClick={() => {
                              const days = editPostingHours.days_of_week || []
                              if (days.includes(idx)) {
                                setEditPostingHours(prev => ({ ...prev, days_of_week: days.filter(d => d !== idx) }))
                              } else {
                                setEditPostingHours(prev => ({ ...prev, days_of_week: [...days, idx].sort() }))
                              }
                            }}
                            style={{
                              padding:'4px 8px',
                              borderRadius:'4px',
                              fontSize:'11px',
                              border:'1px solid #e0e0e0',
                              background: (editPostingHours.days_of_week || []).includes(idx) ? '#111' : '#fff',
                              color: (editPostingHours.days_of_week || []).includes(idx) ? '#fff' : '#666',
                              cursor:'pointer'
                            }}
                          >
                            {day}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Autopilot */}
              <div style={{borderTop:'1px solid #e8e8e8',paddingTop:'20px'}}>
                <div style={{display:'flex',alignItems:'center',gap:'12px',marginBottom:'12px'}}>
                  <label style={{fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999'}}>Autopilot</label>
                  <label style={{display:'flex',alignItems:'center',gap:'6px',cursor:'pointer'}}>
                    <input
                      type="checkbox"
                      checked={editAutopilot.enabled}
                      onChange={(e) => setEditAutopilot(prev => ({ ...prev, enabled: e.target.checked }))}
                    />
                    <span style={{fontSize:'12px',color:'#666'}}>Enable</span>
                  </label>
                </div>
                {editAutopilot.enabled && (
                  <div style={{padding:'12px',background:'#f8f9fa',borderRadius:'8px'}}>
                    <p style={{fontSize:'12px',color:'#666',marginBottom:'12px'}}>
                      Automatically approve and post replies that meet these thresholds.
                    </p>
                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'12px'}}>
                      <div>
                        <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>Min Relevance Score (1-10)</label>
                        <input
                          type="number"
                          min={1}
                          max={10}
                          value={editAutopilot.min_relevance_score}
                          onChange={(e) => setEditAutopilot(prev => ({ ...prev, min_relevance_score: parseInt(e.target.value) || 7 }))}
                          style={{width:'100%',padding:'6px 8px',borderRadius:'4px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                        />
                      </div>
                      <div>
                        <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>Min Confidence (0-1)</label>
                        <input
                          type="number"
                          min={0}
                          max={1}
                          step={0.1}
                          value={editAutopilot.min_confidence}
                          onChange={(e) => setEditAutopilot(prev => ({ ...prev, min_confidence: parseFloat(e.target.value) || 0.8 }))}
                          style={{width:'100%',padding:'6px 8px',borderRadius:'4px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                        />
                      </div>
                    </div>
                    <label style={{display:'flex',alignItems:'center',gap:'6px',marginTop:'12px',cursor:'pointer'}}>
                      <input
                        type="checkbox"
                        checked={editAutopilot.require_no_product_mention}
                        onChange={(e) => setEditAutopilot(prev => ({ ...prev, require_no_product_mention: e.target.checked }))}
                      />
                      <span style={{fontSize:'12px',color:'#666'}}>Only auto-approve if product is not mentioned</span>
                    </label>
                  </div>
                )}
              </div>

              {/* Tweet Targeting */}
              <div style={{borderTop:'1px solid #e8e8e8',paddingTop:'20px'}}>
                <label style={{display:'block',fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'12px'}}>Tweet Targeting</label>
                <p style={{fontSize:'12px',color:'#666',marginBottom:'12px'}}>
                  Pre-filter tweets before AI scoring to save costs.
                </p>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'12px'}}>
                  <div>
                    <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>Max Age (hours)</label>
                    <input
                      type="number"
                      min={1}
                      max={168}
                      value={editTargeting.max_tweet_age_hours}
                      onChange={(e) => setEditTargeting(prev => ({ ...prev, max_tweet_age_hours: parseInt(e.target.value) || 24 }))}
                      style={{width:'100%',padding:'6px 8px',borderRadius:'4px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                    />
                  </div>
                  <div>
                    <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>Min Likes</label>
                    <input
                      type="number"
                      min={0}
                      max={1000}
                      value={editTargeting.min_likes}
                      onChange={(e) => setEditTargeting(prev => ({ ...prev, min_likes: parseInt(e.target.value) || 2 }))}
                      style={{width:'100%',padding:'6px 8px',borderRadius:'4px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                    />
                  </div>
                  <div>
                    <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>Min Followers</label>
                    <input
                      type="number"
                      min={0}
                      max={100000}
                      value={editTargeting.min_author_followers}
                      onChange={(e) => setEditTargeting(prev => ({ ...prev, min_author_followers: parseInt(e.target.value) || 50 }))}
                      style={{width:'100%',padding:'6px 8px',borderRadius:'4px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                    />
                  </div>
                  <div>
                    <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>Max Replies</label>
                    <input
                      type="number"
                      min={1}
                      max={1000}
                      value={editTargeting.max_reply_count}
                      onChange={(e) => setEditTargeting(prev => ({ ...prev, max_reply_count: parseInt(e.target.value) || 100 }))}
                      style={{width:'100%',padding:'6px 8px',borderRadius:'4px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                    />
                  </div>
                  <div>
                    <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>Min Opportunity</label>
                    <input
                      type="number"
                      min={0}
                      max={500}
                      value={editTargeting.min_opportunity_score}
                      onChange={(e) => setEditTargeting(prev => ({ ...prev, min_opportunity_score: parseInt(e.target.value) || 10 }))}
                      style={{width:'100%',padding:'6px 8px',borderRadius:'4px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                    />
                  </div>
                  <div>
                    <label style={{display:'block',fontSize:'10px',color:'#999',marginBottom:'4px'}}>Max AI Calls/Run</label>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={editTargeting.max_ai_calls_per_run}
                      onChange={(e) => setEditTargeting(prev => ({ ...prev, max_ai_calls_per_run: parseInt(e.target.value) || 20 }))}
                      style={{width:'100%',padding:'6px 8px',borderRadius:'4px',border:'1px solid #e0e0e0',fontSize:'12px'}}
                    />
                  </div>
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
              {(selectedProduct.website_url || selectedProduct.twitter_handle) && (
                <div>
                  <div style={{fontSize:'12px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'8px'}}>Product Mention</div>
                  <div style={{padding:'12px',background:'#f8f9fa',borderRadius:'8px'}}>
                    <div style={{fontSize:'12px',color:'#666',marginBottom:'6px'}}>
                      Strategy: <span style={{fontWeight:500,color:'#111',textTransform:'capitalize'}}>{selectedProduct.mention_strategy || 'website'}</span>
                    </div>
                    {selectedProduct.website_url && (
                      <div style={{fontSize:'12px',color:'#666'}}>Website: <span style={{fontWeight:500,color:'#111'}}>{selectedProduct.website_url}</span></div>
                    )}
                    {selectedProduct.twitter_handle && (
                      <div style={{fontSize:'12px',color:'#666',marginTop:'4px'}}>Twitter: <span style={{fontWeight:500,color:'#111'}}>{selectedProduct.twitter_handle}</span></div>
                    )}
                  </div>
                </div>
              )}
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
