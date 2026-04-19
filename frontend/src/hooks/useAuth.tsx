import { createContext, useContext, useState, ReactNode } from 'react'

interface AuthUser { user_id: string; email: string; name: string }
interface AuthCtx {
  user: AuthUser | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  // 100% AUTH BYPASS: The frontend acts as if it is perfectly logged in from the very first render.
  const [user] = useState<AuthUser>({
    user_id: '00000000-0000-0000-0000-000000000000',
    email: 'guest@wozly.local',
    name: 'Guest Student'
  })

  const login = async () => {}
  const register = async () => {}
  const logout = () => {}

  return <AuthContext.Provider value={{ user, isLoading: false, login, register, logout }}>{children}</AuthContext.Provider>
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
