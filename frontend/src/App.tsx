import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { AuthProvider, useAuth } from './hooks/useAuth'
import { ErrorBoundary } from './components/ErrorBoundary'
import Register from './pages/Register'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import Quiz from './pages/Quiz'
import Profile from './pages/Profile'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1 } } })

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  if (isLoading) return (
    <div className="bg-animated min-h-screen flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
    </div>
  )
  return user ? <>{children}</> : <Navigate to="/login" replace />
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  if (isLoading) return null
  return user ? <Navigate to="/dashboard" replace /> : <>{children}</>
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<Navigate to="/onboarding" replace />} />
            <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
            <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
            <Route path="/onboarding" element={<ProtectedRoute><ErrorBoundary><Onboarding /></ErrorBoundary></ProtectedRoute>} />
            <Route path="/dashboard" element={<ProtectedRoute><ErrorBoundary><Dashboard /></ErrorBoundary></ProtectedRoute>} />
            <Route path="/quiz/:weekId" element={<ProtectedRoute><ErrorBoundary><Quiz /></ErrorBoundary></ProtectedRoute>} />
            <Route path="/profile" element={<ProtectedRoute><ErrorBoundary><Profile /></ErrorBoundary></ProtectedRoute>} />
          </Routes>
          <Toaster
            position="top-right"
            toastOptions={{
              style: { background: '#0F172A', color: '#F1F5F9', border: '1px solid rgba(99,102,241,0.2)' },
              success: { iconTheme: { primary: '#10B981', secondary: '#0F172A' } },
              error: { iconTheme: { primary: '#F43F5E', secondary: '#0F172A' } },
            }}
          />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
