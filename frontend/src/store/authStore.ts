/**
 * Auth Store - Zustand state management for authentication
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User, LoginCredentials } from '@/types'
import { authAPI } from '@/services/api'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  // Actions
  login: (credentials: LoginCredentials) => Promise<void>
  logout: () => Promise<void>
  clearError: () => void
  setUser: (user: User) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (credentials: LoginCredentials) => {
        set({ isLoading: true, error: null })
        try {
          const response = await authAPI.login(credentials)

          // Store tokens
          localStorage.setItem('access_token', response.access)
          localStorage.setItem('refresh_token', response.refresh)

          set({
            user: response.user,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          })
        } catch (error: any) {
          const errorMessage =
            error.response?.data?.detail || 'Error de autenticación'
          set({
            error: errorMessage,
            isLoading: false,
            isAuthenticated: false,
          })
          throw error
        }
      },

      logout: async () => {
        try {
          await authAPI.logout()
        } finally {
          set({
            user: null,
            isAuthenticated: false,
            error: null,
          })
        }
      },

      clearError: () => set({ error: null }),

      setUser: (user: User) => set({ user, isAuthenticated: true }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
