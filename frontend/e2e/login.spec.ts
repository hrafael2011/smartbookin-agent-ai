import { test, expect } from '@playwright/test'

const mockMetrics = {
  today: {
    total_appointments: 0,
    confirmed: 0,
    pending: 0,
    cancelled: 0,
    revenue: '0',
  },
  week: { total_appointments: 0, revenue: '0', occupancy_rate: 0 },
  month: { total_appointments: 0, revenue: '0', new_customers: 0 },
  top_services: [] as { service_name: string; count: number; revenue: string }[],
  recent_appointments: [],
  upcoming_appointments: [],
}

const mockBusiness = {
  id: 1,
  owner_id: 1,
  name: 'Negocio E2E',
  phone_number: '+18090000000',
  category: 'barbershop',
  is_active: true,
  daily_notification_enabled: true,
  created_at: '2026-01-01T00:00:00Z',
}

test.describe('Autenticación (API mockeada)', () => {
  test('login exitoso navega al dashboard', async ({ page }) => {
    await page.route('**/api/auth/token**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'test-access-token',
          refresh: 'test-refresh-token',
          token_type: 'bearer',
          user: {
            id: 1,
            name: 'Usuario E2E',
            email: 'e2e@test.com',
            email_verified: true,
            created_at: new Date().toISOString(),
          },
        }),
      })
    })

    await page.route('**/api/businesses/**', async (route) => {
      const method = route.request().method()
      const u = route.request().url()
      const isList = method === 'GET' && /\/api\/businesses\/?(\?.*)?$/.test(u)
      if (isList) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([mockBusiness]),
        })
        return
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    })

    await page.route('**/api/dashboard/metrics/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockMetrics),
      })
    })

    await page.goto('/login')
    await expect(page.getByRole('heading', { name: /SmartBooking/i })).toBeVisible()

    await page.locator('#email').fill('e2e@test.com')
    await page.locator('#password').fill('secret123')
    await page.getByRole('button', { name: /Iniciar sesión/i }).click()

    await expect(page).toHaveURL(/\/dashboard/)
    await expect(page.getByRole('heading', { name: /^Dashboard$/ })).toBeVisible()
    await expect(page.getByText('Negocio E2E', { exact: true }).first()).toBeVisible()
  })

  test('página de registro es accesible', async ({ page }) => {
    await page.goto('/register')
    await expect(page.getByRole('heading', { name: /Crear cuenta/i })).toBeVisible()
  })
})
