/** App shell: sticky header with brand, nav, theme toggle, and auth state; renders the route below. */

import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Briefcase, LogIn, LogOut, Moon, Sun } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'

const THEME_KEY = 'mindbridge_theme'

function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light')
  }, [dark])
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
      onClick={() => setDark((d) => !d)}
    >
      {dark ? <Sun /> : <Moon />}
    </Button>
  )
}

function navLinkClass({ isActive }: { isActive: boolean }) {
  return cn(
    'text-sm font-medium transition-colors hover:text-foreground',
    isActive ? 'text-foreground' : 'text-muted-foreground',
  )
}

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur">
        <div className="container flex h-16 items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2 text-lg font-semibold">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Briefcase className="h-4 w-4" />
            </span>
            MindBridge<span className="text-primary">.ai</span>
          </Link>

          <nav className="flex items-center gap-4 sm:gap-6">
            <NavLink to="/" end className={navLinkClass}>
              Match
            </NavLink>
            {user && (
              <NavLink to="/profile" className={navLinkClass}>
                {user.role === 'hirer' ? 'My postings' : 'My profile'}
              </NavLink>
            )}
            {user && (
              <NavLink to="/history" className={navLinkClass}>
                History
              </NavLink>
            )}
            <ThemeToggle />
            {user ? (
              <div className="flex items-center gap-3">
                <Badge variant="secondary" className="hidden capitalize sm:inline-flex">
                  {user.role}
                </Badge>
                <span className="hidden max-w-[14rem] truncate text-sm text-muted-foreground md:inline">
                  {user.email}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    logout()
                    navigate('/')
                  }}
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </Button>
              </div>
            ) : (
              <Button size="sm" onClick={() => navigate('/login')}>
                <LogIn className="h-4 w-4" />
                Sign in
              </Button>
            )}
          </nav>
        </div>
      </header>

      <main className="container py-8">
        <Outlet />
      </main>
    </div>
  )
}
