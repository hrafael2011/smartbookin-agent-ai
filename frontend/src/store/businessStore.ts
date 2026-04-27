/**
 * Business Store - Zustand state management for business context
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Business } from '@/types'
import { businessAPI } from '@/services/api'

interface BusinessState {
  currentBusiness: Business | null
  businesses: Business[]
  isLoading: boolean
  error: string | null

  // Actions
  fetchBusinesses: () => Promise<void>
  setCurrentBusiness: (business: Business) => void
  updateBusiness: (id: number, data: Partial<Business>) => Promise<void>
  clearError: () => void
}

export const useBusinessStore = create<BusinessState>()(
  persist(
    (set, get) => ({
      currentBusiness: null,
      businesses: [],
      isLoading: false,
      error: null,

      fetchBusinesses: async () => {
        set({ isLoading: true, error: null })
        try {
          const businesses = await businessAPI.list()
          set({
            businesses,
            isLoading: false,
            // Auto-select first business if none selected
            currentBusiness: get().currentBusiness || businesses[0] || null,
          })
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Error cargando negocios',
            isLoading: false,
          })
          throw error
        }
      },

      setCurrentBusiness: (business: Business) => {
        set({ currentBusiness: business })
      },

      updateBusiness: async (id: number, data: Partial<Business>) => {
        set({ isLoading: true, error: null })
        try {
          const updated = await businessAPI.update(id, data)

          // Update in list
          const businesses = get().businesses.map((b) =>
            b.id === id ? updated : b
          )

          // Update current if it's the same
          const currentBusiness =
            get().currentBusiness?.id === id ? updated : get().currentBusiness

          set({
            businesses,
            currentBusiness,
            isLoading: false,
          })
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Error actualizando negocio',
            isLoading: false,
          })
          throw error
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'business-storage',
      partialize: (state) => ({
        currentBusiness: state.currentBusiness,
        businesses: state.businesses,
      }),
    }
  )
)
