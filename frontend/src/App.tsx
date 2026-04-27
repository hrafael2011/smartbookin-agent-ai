/**
 * Main App Component with Routing
 */
import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from './store/authStore'
import { Toaster } from 'sonner'
import DashboardLayout from './components/layouts/DashboardLayout'
import { NotFound } from './pages/NotFound'
import { ErrorBoundary } from './components/ui/ErrorBoundary'

const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))
const VerifyEmail = lazy(() => import('./pages/VerifyEmail'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const TestUI = lazy(() => import('./pages/TestUI'))
const Calendar = lazy(() => import('./pages/Calendar').then((mod) => ({ default: mod.Calendar })))
const Appointments = lazy(() => import('./pages/Appointments').then((mod) => ({ default: mod.Appointments })))
const Customers = lazy(() => import('./pages/Customers').then((mod) => ({ default: mod.Customers })))
const Services = lazy(() => import('./pages/Services').then((mod) => ({ default: mod.Services })))
const Schedule = lazy(() => import('./pages/Schedule').then((mod) => ({ default: mod.Schedule })))
const TelegramIntegration = lazy(() => import('./pages/TelegramIntegration'))
const BusinessSettings = lazy(() => import('./pages/BusinessSettings'))

// Create QueryClient instance
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

// Protected Route Component
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function PageLoader() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted-foreground">
      Cargando...
    </div>
  )
}

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Toaster position="top-right" richColors closeButton />
          <Suspense fallback={<PageLoader />}>
            <Routes>
              {/* Public Routes */}
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/verify-email" element={<VerifyEmail />} />
              <Route path="/test-ui" element={<TestUI />} />

              {/* Protected Routes */}
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <DashboardLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="calendar" element={<Calendar />} />
                <Route path="appointments" element={<Appointments />} />
                <Route path="customers" element={<Customers />} />
                <Route path="services" element={<Services />} />
                <Route path="schedule" element={<Schedule />} />
                <Route path="telegram" element={<TelegramIntegration />} />
                <Route path="settings" element={<BusinessSettings />} />
              </Route>

              {/* 404 */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

export default App
