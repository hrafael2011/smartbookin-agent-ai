import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAuthStore } from './authStore'

vi.mock('@/services/api', () => ({
  authAPI: {
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
  },
}))

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockAuthAPI = vi.mocked((await import('@/services/api')).authAPI)

describe('authStore', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    })
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('starts with unauthenticated state', () => {
    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
    expect(state.user).toBeNull()
    expect(state.error).toBeNull()
  })

  it('sets loading to true during login', async () => {
    let resolveLogin!: (value: unknown) => void
    mockAuthAPI.login.mockReturnValue(new Promise((r) => { resolveLogin = r }))

    const loginPromise = useAuthStore.getState().login({ email: 'test@test.com', password: '123' })
    expect(useAuthStore.getState().isLoading).toBe(true)

    resolveLogin({ access: 'tok', refresh: 'ref', user: { id: 1, name: 'T', email: 't@t.com', phone: '', email_verified: true, created_at: '' } })
    await loginPromise
    expect(useAuthStore.getState().isLoading).toBe(false)
  })

  it('handles login success', async () => {
    const mockUser = {
      id: 1,
      name: 'Test',
      email: 'test@test.com',
      phone: '809-555-0100',
      email_verified: true,
      created_at: '2026-01-01T00:00:00Z',
    }
    mockAuthAPI.login.mockResolvedValue({
      access: 'mock-access-token',
      refresh: 'mock-refresh-token',
      user: mockUser,
    })

    await useAuthStore.getState().login({ email: 'test@test.com', password: '123' })

    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(true)
    expect(state.user).toEqual(mockUser)
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
    expect(localStorage.getItem('access_token')).toBe('mock-access-token')
    expect(localStorage.getItem('refresh_token')).toBe('mock-refresh-token')
  })

  it('handles login failure', async () => {
    mockAuthAPI.login.mockRejectedValue({
      response: { data: { detail: 'Credenciales inválidas' } },
    })

    try {
      await useAuthStore.getState().login({ email: 'wrong@test.com', password: 'wrong' })
    } catch {
      // expected
    }

    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
    expect(state.user).toBeNull()
    expect(state.error).toBe('Credenciales inválidas')
    expect(state.isLoading).toBe(false)
  })

  it('clears error', () => {
    useAuthStore.setState({ error: 'Some error' })
    useAuthStore.getState().clearError()
    expect(useAuthStore.getState().error).toBeNull()
  })

  it('sets user directly with setUser', () => {
    const mockUser = {
      id: 1,
      name: 'Test',
      email: 'test@test.com',
      phone: '809-555-0100',
      email_verified: true,
      created_at: '2026-01-01T00:00:00Z',
    }
    useAuthStore.getState().setUser(mockUser)
    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(true)
    expect(state.user).toEqual(mockUser)
  })
})
