'use client'

import { useRouter } from 'next/navigation'
import { useProducts } from '@/lib/product-context'
import { PLATFORM_COLORS } from '@/lib/constants'
import { useIsMobile } from '@/lib/hooks'

export default function ProductsPage() {
  const router = useRouter()
  const { products, loading, error, selectProduct, refreshProducts } = useProducts()
  const { isMobile } = useIsMobile()

  function handleSelectProduct(productId: string) {
    selectProduct(productId)
    router.push('/queue')
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px', color: '#999', fontSize: '14px' }}>
        Loading products...
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ maxWidth: '600px' }}>
        <div style={{ padding: '20px', background: '#ffebee', borderRadius: '12px', border: '1px solid #ffcdd2' }}>
          <div style={{ fontSize: '14px', fontWeight: 600, color: '#c62828', marginBottom: '8px' }}>Failed to load products</div>
          <div style={{ fontSize: '13px', color: '#e53935', marginBottom: '12px' }}>{error}</div>
          <button
            onClick={() => refreshProducts()}
            style={{ padding: '8px 16px', borderRadius: '8px', background: '#c62828', color: '#fff', fontSize: '14px', fontWeight: 600, border: 'none', cursor: 'pointer', minHeight: '44px' }}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: isMobile ? '100%' : '900px' }}>
      <div style={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row', alignItems: isMobile ? 'stretch' : 'flex-end', justifyContent: 'space-between', gap: isMobile ? '16px' : undefined, marginBottom: '32px' }}>
        <div>
          <h1 style={{ fontSize: isMobile ? '24px' : '28px', fontWeight: 600, color: '#111', lineHeight: 1 }}>Products</h1>
          <p style={{ fontSize: '14px', color: '#999', marginTop: '6px' }}>
            {products.length} {products.length === 1 ? 'product' : 'products'}
          </p>
        </div>
        <button
          onClick={() => router.push('/onboarding')}
          style={{ padding: '10px 20px', borderRadius: '10px', background: '#111', color: '#fff', fontSize: '14px', fontWeight: 600, border: 'none', cursor: 'pointer', minHeight: '44px', width: isMobile ? '100%' : undefined }}
        >
          + Add Product
        </button>
      </div>

      {products.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '80px 40px', background: '#fafafa', borderRadius: '16px', border: '1px solid #e8e8e8' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📦</div>
          <p style={{ fontSize: '16px', fontWeight: 500, color: '#111', marginBottom: '8px' }}>No products yet</p>
          <p style={{ fontSize: '14px', color: '#666', marginBottom: '24px' }}>Create your first product to start generating replies</p>
          <button
            onClick={() => router.push('/onboarding')}
            style={{ padding: '12px 24px', borderRadius: '10px', background: '#111', color: '#fff', fontSize: '14px', fontWeight: 600, border: 'none', cursor: 'pointer', minHeight: '44px' }}
          >
            Create Product
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
          {products.map((product) => {
            const platforms = Object.keys(product.keywords || {}).filter(p => (product.keywords[p] || []).length > 0)
            const keywordCount = Object.values(product.keywords || {}).flat().length

            return (
              <div
                key={product.id}
                onClick={() => handleSelectProduct(product.id)}
                style={{
                  padding: '20px',
                  background: '#fff',
                  borderRadius: '16px',
                  border: '1px solid #e8e8e8',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = '#111'
                  e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.1)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = '#e8e8e8'
                  e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.04)'
                }}
              >
                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#111', margin: 0 }}>{product.name}</h3>
                  <div
                    style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      background: product.active ? '#22c55e' : '#999',
                    }}
                    title={product.active ? 'Active' : 'Inactive'}
                  />
                </div>

                {/* Description */}
                {product.description && (
                  <p style={{ fontSize: isMobile ? '14px' : '13px', color: '#666', lineHeight: 1.5, marginBottom: '16px', overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as const }}>
                    {product.description}
                  </p>
                )}

                {/* Platform badges */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
                  {platforms.map(platform => (
                    <span
                      key={platform}
                      style={{
                        fontSize: '10px',
                        fontWeight: 700,
                        padding: '3px 8px',
                        borderRadius: '12px',
                        color: '#fff',
                        background: PLATFORM_COLORS[platform] || '#666',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                      }}
                    >
                      {platform}
                    </span>
                  ))}
                </div>

                {/* Stats */}
                <div style={{ display: 'flex', gap: '16px', paddingTop: '12px', borderTop: '1px solid #f0f0f0' }}>
                  <div>
                    <div style={{ fontSize: '20px', fontWeight: 600, color: '#111' }}>{product.pending_count || 0}</div>
                    <div style={{ fontSize: isMobile ? '14px' : '11px', color: '#999', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Pending</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '20px', fontWeight: 600, color: '#111' }}>{keywordCount}</div>
                    <div style={{ fontSize: isMobile ? '14px' : '11px', color: '#999', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Keywords</div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
