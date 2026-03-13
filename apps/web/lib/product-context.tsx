'use client'

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react'
import { apiFetch } from './api'

/**
 * ProductContext provides multi-product support across the dashboard.
 *
 * Data Flow:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │  1. User logs in                                                │
 * │  2. Dashboard layout mounts ProductProvider                     │
 * │  3. fetchProducts() calls GET /products (auth required)         │
 * │  4. If products exist:                                          │
 * │     - Check localStorage for previously selected product        │
 * │     - If valid, use it; otherwise select first product          │
 * │  5. If no products: parent redirects to /onboarding             │
 * │  6. All child pages read selectedProduct from context           │
 * │  7. User can switch via selectProduct() in sidebar dropdown     │
 * └─────────────────────────────────────────────────────────────────┘
 */

export type Product = {
  id: string
  name: string
  slug: string
  description: string
  system_prompt: string
  keywords: Record<string, string[]>
  tone: string
  active: boolean
  user_id: string
  created_at: string
  // Counts populated by backend
  pending_count?: number
  posted_count?: number
  // Fire rate control fields
  max_replies_per_day?: Record<string, number>
  max_replies_per_hour?: Record<string, number>
  min_delay_between_posts?: number
  posting_hours?: {
    enabled: boolean
    timezone: string
    start_hour: number
    end_hour: number
    days_of_week: number[]
  }
  autopilot?: {
    enabled: boolean
    min_relevance_score: number
    min_confidence: number
    require_no_product_mention: boolean
  }
  targeting?: {
    max_tweet_age_hours: number
    min_likes: number
    min_author_followers: number
    max_reply_count: number
    min_opportunity_score: number
    max_ai_calls_per_run: number
  }
  // Product mention configuration
  website_url?: string
  twitter_handle?: string
  mention_strategy?: 'website' | 'handle' | 'mix'
}

type ProductContextType = {
  products: Product[]
  selectedProduct: Product | null
  selectedProductId: string | null
  loading: boolean
  error: string | null
  selectProduct: (productId: string) => void
  refreshProducts: () => Promise<void>
}

const ProductContext = createContext<ProductContextType | null>(null)

const STORAGE_KEY = 'operative1_selected_product'

export function ProductProvider({ children }: { children: ReactNode }) {
  const [products, setProducts] = useState<Product[]>([])
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const selectedProduct = products.find(p => p.id === selectedProductId) || null

  // Load selected product from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        setSelectedProductId(stored)
      }
    } catch {
      // localStorage not available or corrupted, ignore
    }
  }, [])

  // Sync selected product to localStorage
  useEffect(() => {
    if (selectedProductId) {
      try {
        localStorage.setItem(STORAGE_KEY, selectedProductId)
      } catch {
        // localStorage quota exceeded or not available, ignore
      }
    }
  }, [selectedProductId])

  const fetchProducts = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiFetch<Product[]>('/products')
      setProducts(data || [])

      // Auto-select logic
      if (data && data.length > 0) {
        const storedId = localStorage.getItem(STORAGE_KEY)
        const storedValid = storedId && data.some(p => p.id === storedId)

        if (storedValid) {
          setSelectedProductId(storedId)
        } else {
          // Select first product if stored one is invalid
          setSelectedProductId(data[0].id)
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load products')
    } finally {
      setLoading(false)
    }
  }, [])

  // Fetch products on mount
  useEffect(() => {
    fetchProducts()
  }, [fetchProducts])

  const selectProduct = useCallback((productId: string) => {
    const exists = products.some(p => p.id === productId)
    if (exists) {
      setSelectedProductId(productId)
    }
  }, [products])

  const refreshProducts = useCallback(async () => {
    await fetchProducts()
  }, [fetchProducts])

  return (
    <ProductContext.Provider
      value={{
        products,
        selectedProduct,
        selectedProductId,
        loading,
        error,
        selectProduct,
        refreshProducts,
      }}
    >
      {children}
    </ProductContext.Provider>
  )
}

export function useProducts() {
  const context = useContext(ProductContext)
  if (!context) {
    throw new Error('useProducts must be used within ProductProvider')
  }
  return context
}
