import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import type { ReactElement } from 'react'

import { Layout } from '@/components/Layout'
import { AuthPage } from '@/pages/AuthPage'
import { HistoryPage } from '@/pages/HistoryPage'
import { MatchPage } from '@/pages/MatchPage'
import { ProfilePage } from '@/pages/ProfilePage'
import { useAuth } from '@/context/AuthContext'

/** Gate a route behind auth; while the token is being validated, show a spinner (avoids a flash
 *  redirect to /login on refresh). Unauthenticated users are sent to /login, remembering where. */
function RequireAuth({ children }: { children: ReactElement }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-24 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        Loading…
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<MatchPage />} />
        <Route
          path="profile"
          element={
            <RequireAuth>
              <ProfilePage />
            </RequireAuth>
          }
        />
        <Route
          path="history"
          element={
            <RequireAuth>
              <HistoryPage />
            </RequireAuth>
          }
        />
      </Route>
      <Route path="/login" element={<AuthPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
