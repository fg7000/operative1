'use client'

import { useState, useEffect } from 'react'

/**
 * Responsive breakpoint hook for mobile/tablet detection.
 * SSR-safe: defaults to desktop, updates on client mount.
 */
export function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false)
  const [isTablet, setIsTablet] = useState(false)

  useEffect(() => {
    const mobileQuery = window.matchMedia('(max-width: 767px)')
    const tabletQuery = window.matchMedia('(max-width: 1023px)')

    function update() {
      setIsMobile(mobileQuery.matches)
      setIsTablet(tabletQuery.matches)
    }

    update()
    mobileQuery.addEventListener('change', update)
    tabletQuery.addEventListener('change', update)

    return () => {
      mobileQuery.removeEventListener('change', update)
      tabletQuery.removeEventListener('change', update)
    }
  }, [])

  return { isMobile, isTablet }
}
