'use client'
import { useEffect, useState } from 'react'
import { useProducts } from '@/lib/product-context'
import { apiFetch } from '@/lib/api'
import { MODE_COLORS } from '@/lib/constants'
import { useIsMobile } from '@/lib/hooks'

type DashboardData = {
  status_counts: Record<string, number>
  mode_breakdown: Record<string, number>
  mode_averages: Record<string, { avg_likes: number; avg_impressions: number }>
  score_distribution: Record<string, number>
  daily_timeline: Array<{ date: string; count: number }>
  total_items: number
}

const STATUS_COLORS: Record<string, string> = {
  posted: '#22c55e',
  pending: '#f59e0b',
  failed: '#ef4444',
  rejected: '#6b7280',
}

export default function AnalyticsPage() {
  const { selectedProduct, selectedProductId, loading: productsLoading } = useProducts()
  const { isMobile } = useIsMobile()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (selectedProductId) {
      fetchAnalytics()
    }
  }, [selectedProductId])

  async function fetchAnalytics() {
    if (!selectedProductId) return
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch<DashboardData>(`/analytics/dashboard?product_id=${selectedProductId}`)
      setData(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load analytics')
    } finally {
      setLoading(false)
    }
  }

  if (productsLoading) {
    return <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'200px',color:'#999',fontSize:'14px'}}>Loading...</div>
  }

  if (!selectedProduct) {
    return (
      <div style={{textAlign:'center',padding:'80px 40px',background:'#fafafa',borderRadius:'16px',border:'1px solid #e8e8e8'}}>
        <div style={{fontSize:'32px',marginBottom:'12px'}}>📊</div>
        <p style={{fontSize:'15px',fontWeight:500,color:'#111'}}>Select a product</p>
        <p style={{fontSize:'14px',color:'#999',marginTop:'4px'}}>Choose a product from the sidebar to view its analytics</p>
      </div>
    )
  }

  if (loading) {
    return <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'200px',color:'#999',fontSize:'14px'}}>Loading analytics...</div>
  }

  if (error) {
    return (
      <div style={{maxWidth:'600px'}}>
        <div style={{padding:'20px',background:'#ffebee',borderRadius:'12px',border:'1px solid #ffcdd2'}}>
          <div style={{fontSize:'14px',fontWeight:600,color:'#c62828',marginBottom:'8px'}}>Failed to load analytics</div>
          <div style={{fontSize:'14px',color:'#e53935',marginBottom:'12px'}}>{error}</div>
          <button
            onClick={fetchAnalytics}
            style={{padding:'8px 16px',borderRadius:'8px',background:'#c62828',color:'#fff',fontSize:'14px',fontWeight:600,border:'none',cursor:'pointer',minHeight:'44px'}}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (!data) return null

  const maxDailyCount = Math.max(...data.daily_timeline.map(d => d.count), 1)

  return (
    <div style={{maxWidth: isMobile ? '100%' : '900px'}}>
      <div style={{marginBottom:'32px'}}>
        <h1 style={{fontSize: isMobile ? '24px' : '28px',fontWeight:600,color:'#111',lineHeight:1}}>Analytics</h1>
        <p style={{fontSize:'14px',color:'#999',marginTop:'6px'}}>{selectedProduct.name} — {data.total_items} total items</p>
      </div>

      {/* Status Overview Cards */}
      <div style={{display:'grid',gridTemplateColumns: isMobile ? 'repeat(2, 1fr)' : 'repeat(4, 1fr)',gap:'16px',marginBottom:'32px'}}>
        {Object.entries(data.status_counts).map(([status, count]) => (
          <div key={status} style={{padding: isMobile ? '16px' : '20px',background:'#fff',borderRadius:'12px',border:'1px solid #e8e8e8',boxShadow:'0 2px 8px rgba(0,0,0,0.04)'}}>
            <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'8px'}}>
              <div style={{width:'10px',height:'10px',borderRadius:'50%',background:STATUS_COLORS[status] || '#999'}}></div>
              <span style={{fontSize: isMobile ? '14px' : '12px',fontWeight:600,textTransform:'uppercase',letterSpacing:'0.05em',color:'#666'}}>{status}</span>
            </div>
            <div style={{fontSize: isMobile ? '28px' : '32px',fontWeight:700,color:'#111'}}>{count}</div>
          </div>
        ))}
      </div>

      {/* Two-column grid for charts */}
      <div style={{display:'grid',gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr',gap:'24px',marginBottom:'32px'}}>
        {/* Mode Breakdown */}
        <div style={{padding:'24px',background:'#fff',borderRadius:'12px',border:'1px solid #e8e8e8',boxShadow:'0 2px 8px rgba(0,0,0,0.04)'}}>
          <h3 style={{fontSize:'14px',fontWeight:600,color:'#111',marginBottom:'20px'}}>Reply Mode Distribution</h3>
          <div style={{display:'flex',flexDirection:'column',gap:'12px'}}>
            {Object.entries(data.mode_breakdown).filter(([mode]) => mode !== 'unknown').map(([mode, count]) => {
              const total = Object.values(data.mode_breakdown).reduce((a, b) => a + b, 0)
              const pct = total > 0 ? Math.round((count / total) * 100) : 0
              const modeStyle = MODE_COLORS[mode] || { bg: '#f0f0f0', color: '#555' }
              return (
                <div key={mode}>
                  <div style={{display:'flex',justifyContent:'space-between',marginBottom:'4px'}}>
                    <span style={{fontSize:'14px',fontWeight:500,color:'#333',textTransform:'capitalize'}}>{mode.replace('_', ' ')}</span>
                    <span style={{fontSize:'14px',color:'#999'}}>{count} ({pct}%)</span>
                  </div>
                  <div style={{height:'8px',background:'#f5f5f5',borderRadius:'4px',overflow:'hidden'}}>
                    <div style={{height:'100%',width:`${pct}%`,background:modeStyle.color,borderRadius:'4px',transition:'width 0.3s ease'}}></div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Score Distribution */}
        <div style={{padding:'24px',background:'#fff',borderRadius:'12px',border:'1px solid #e8e8e8',boxShadow:'0 2px 8px rgba(0,0,0,0.04)'}}>
          <h3 style={{fontSize:'14px',fontWeight:600,color:'#111',marginBottom:'20px'}}>Relevance Score Distribution</h3>
          <div style={{display:'flex',flexDirection:'column',gap:'12px'}}>
            {Object.entries(data.score_distribution).map(([bucket, count]) => {
              const total = Object.values(data.score_distribution).reduce((a, b) => a + b, 0)
              const pct = total > 0 ? Math.round((count / total) * 100) : 0
              const bucketColors: Record<string, string> = {
                '0-3': '#ef4444',
                '4-5': '#f59e0b',
                '6-7': '#22c55e',
                '8-10': '#3b82f6',
              }
              return (
                <div key={bucket}>
                  <div style={{display:'flex',justifyContent:'space-between',marginBottom:'4px'}}>
                    <span style={{fontSize:'14px',fontWeight:500,color:'#333'}}>Score {bucket}</span>
                    <span style={{fontSize:'14px',color:'#999'}}>{count} ({pct}%)</span>
                  </div>
                  <div style={{height:'8px',background:'#f5f5f5',borderRadius:'4px',overflow:'hidden'}}>
                    <div style={{height:'100%',width:`${pct}%`,background:bucketColors[bucket] || '#999',borderRadius:'4px',transition:'width 0.3s ease'}}></div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Daily Timeline */}
      <div style={{padding:'24px',background:'#fff',borderRadius:'12px',border:'1px solid #e8e8e8',boxShadow:'0 2px 8px rgba(0,0,0,0.04)'}}>
        <h3 style={{fontSize:'14px',fontWeight:600,color:'#111',marginBottom:'20px'}}>Posts Per Day (Last 30 Days)</h3>
        <div style={{display:'flex',alignItems:'flex-end',gap: isMobile ? '2px' : '4px',height: isMobile ? '80px' : '120px'}}>
          {data.daily_timeline.map((day, i) => {
            const height = maxDailyCount > 0 ? (day.count / maxDailyCount) * 100 : 0
            const date = new Date(day.date)
            const isWeekend = date.getDay() === 0 || date.getDay() === 6
            return (
              <div
                key={day.date}
                style={{flex:1,display:'flex',flexDirection:'column',alignItems:'center',gap:'4px'}}
                title={`${day.date}: ${day.count} posts`}
              >
                <div
                  style={{
                    width:'100%',
                    height:`${Math.max(height, day.count > 0 ? 4 : 0)}%`,
                    background: day.count > 0 ? '#22c55e' : '#f0f0f0',
                    borderRadius:'2px',
                    minHeight: day.count > 0 ? '4px' : '2px',
                    transition:'height 0.3s ease',
                  }}
                ></div>
                {i % 7 === 0 && (
                  <span style={{fontSize:'9px',color:'#999',transform:'rotate(-45deg)',transformOrigin:'center',whiteSpace:'nowrap'}}>
                    {date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </span>
                )}
              </div>
            )
          })}
        </div>
        <div style={{display:'flex',justifyContent:'space-between',marginTop:'16px',paddingTop:'12px',borderTop:'1px solid #f0f0f0'}}>
          <span style={{fontSize:'14px',color:'#999'}}>Total posted: {data.status_counts.posted || 0}</span>
          <span style={{fontSize:'14px',color:'#999'}}>
            Avg: {data.daily_timeline.length > 0 ? (data.daily_timeline.reduce((a, b) => a + b.count, 0) / data.daily_timeline.length).toFixed(1) : 0} per day
          </span>
        </div>
      </div>

      {/* Mode Performance (if we have engagement data) */}
      {Object.values(data.mode_averages).some(m => m.avg_likes > 0 || m.avg_impressions > 0) && (
        <div style={{padding:'24px',background:'#fff',borderRadius:'12px',border:'1px solid #e8e8e8',boxShadow:'0 2px 8px rgba(0,0,0,0.04)',marginTop:'24px'}}>
          <h3 style={{fontSize:'14px',fontWeight:600,color:'#111',marginBottom:'20px'}}>Mode Performance</h3>
          <div style={{display:'grid',gridTemplateColumns: isMobile ? '1fr' : 'repeat(3, 1fr)',gap:'16px'}}>
            {Object.entries(data.mode_averages).map(([mode, stats]) => {
              const modeStyle = MODE_COLORS[mode] || { bg: '#f0f0f0', color: '#555' }
              return (
                <div key={mode} style={{padding:'16px',background:modeStyle.bg,borderRadius:'8px'}}>
                  <div style={{fontSize: isMobile ? '14px' : '12px',fontWeight:600,textTransform:'uppercase',letterSpacing:'0.05em',color:modeStyle.color,marginBottom:'12px'}}>
                    {mode.replace('_', ' ')}
                  </div>
                  <div style={{display:'flex',gap:'16px'}}>
                    <div>
                      <div style={{fontSize:'20px',fontWeight:600,color:'#111'}}>{stats.avg_likes}</div>
                      <div style={{fontSize:'14px',color:'#666'}}>Avg Likes</div>
                    </div>
                    <div>
                      <div style={{fontSize:'20px',fontWeight:600,color:'#111'}}>{stats.avg_impressions}</div>
                      <div style={{fontSize:'14px',color:'#666'}}>Avg Impressions</div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
