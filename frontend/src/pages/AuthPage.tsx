/** Sign in / create account. On success we route back to where the user came from (or `/`).
 *  Also the landing pad for OAuth: the backend callback redirects here with `#token=...` (or
 *  `#error=...`), which we consume from the URL fragment on mount. */

import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Briefcase, Loader2, UserRound, Users } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/context/AuthContext'
import * as api from '@/lib/api'
import { ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { OAuthProviderInfo, Role } from '@/types'

export function AuthPage() {
  const { login, register, loginWithToken } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('hiree')
  const [submitting, setSubmitting] = useState(false)
  const [providers, setProviders] = useState<OAuthProviderInfo[]>([])

  // Which OAuth buttons to show (none, if the backend has no keys configured).
  useEffect(() => {
    let cancelled = false
    api
      .getProviders()
      .then((p) => {
        if (!cancelled) setProviders(p)
      })
      .catch(() => {}) // backend down → the health badge on the match page reports it
    return () => {
      cancelled = true
    }
  }, [])

  // Consume the OAuth callback fragment exactly once (StrictMode double-mounts effects).
  const consumedFragment = useRef(false)
  useEffect(() => {
    if (consumedFragment.current) return
    const fragment = new URLSearchParams(window.location.hash.slice(1))
    const token = fragment.get('token')
    const error = fragment.get('error')
    if (!token && !error) return
    consumedFragment.current = true
    window.history.replaceState(null, '', window.location.pathname) // scrub token from the URL
    if (error) {
      toast.error(error)
      return
    }
    if (token) {
      loginWithToken(token)
        .then((user) => {
          toast.success(`Signed in as ${user.email}`)
          navigate(from, { replace: true })
        })
        .catch(() => toast.error('Sign-in failed — please try again'))
    }
  }, [loginWithToken, navigate, from])

  async function submit(mode: 'login' | 'register', e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    try {
      const user =
        mode === 'login' ? await login(email, password) : await register(email, password, role)
      toast.success(mode === 'login' ? `Welcome back, ${user.email}` : 'Account created')
      navigate(from, { replace: true })
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Something went wrong'
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-md">
        <Link to="/" className="mb-6 flex items-center justify-center gap-2 text-xl font-semibold">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Briefcase className="h-5 w-5" />
          </span>
          MindBridge<span className="text-primary">.ai</span>
        </Link>

        <Card>
          <Tabs defaultValue="login">
            <CardHeader className="gap-4">
              <div className="space-y-1 text-center">
                <CardTitle className="text-2xl">Welcome</CardTitle>
                <CardDescription>
                  Matching works without an account — sign in to save your match history.
                </CardDescription>
              </div>
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="login">Sign in</TabsTrigger>
                <TabsTrigger value="register">Create account</TabsTrigger>
              </TabsList>
            </CardHeader>

            <CardContent>
              {/* Sign in */}
              <TabsContent value="login" className="mt-0">
                <form className="space-y-4" onSubmit={(e) => submit('login', e)}>
                  <Field
                    id="login-email"
                    label="Email"
                    type="email"
                    value={email}
                    onChange={setEmail}
                    autoComplete="email"
                  />
                  <Field
                    id="login-password"
                    label="Password"
                    type="password"
                    value={password}
                    onChange={setPassword}
                    autoComplete="current-password"
                  />
                  <SubmitButton submitting={submitting}>Sign in</SubmitButton>
                </form>
                <OAuthButtons providers={providers} role={role} />
              </TabsContent>

              {/* Create account */}
              <TabsContent value="register" className="mt-0">
                <form className="space-y-4" onSubmit={(e) => submit('register', e)}>
                  <Field
                    id="reg-email"
                    label="Email"
                    type="email"
                    value={email}
                    onChange={setEmail}
                    autoComplete="email"
                  />
                  <Field
                    id="reg-password"
                    label="Password"
                    type="password"
                    value={password}
                    onChange={setPassword}
                    autoComplete="new-password"
                    hint="At least 6 characters."
                  />
                  <div className="space-y-1.5">
                    <Label>I am a…</Label>
                    <div className="grid grid-cols-2 gap-3">
                      <RoleOption
                        active={role === 'hiree'}
                        onClick={() => setRole('hiree')}
                        icon={<UserRound className="h-4 w-4" />}
                        title="Job seeker"
                        subtitle="Find best-fit jobs"
                      />
                      <RoleOption
                        active={role === 'hirer'}
                        onClick={() => setRole('hirer')}
                        icon={<Users className="h-4 w-4" />}
                        title="Employer"
                        subtitle="Find candidates"
                      />
                    </div>
                  </div>
                  <SubmitButton submitting={submitting}>Create account</SubmitButton>
                </form>
                <OAuthButtons providers={providers} role={role} />
              </TabsContent>
            </CardContent>
          </Tabs>
        </Card>
      </div>
    </div>
  )
}

function Field(props: {
  id: string
  label: string
  type: string
  value: string
  onChange: (v: string) => void
  autoComplete?: string
  hint?: string
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={props.id}>{props.label}</Label>
      <Input
        id={props.id}
        type={props.type}
        value={props.value}
        autoComplete={props.autoComplete}
        onChange={(e) => props.onChange(e.target.value)}
        required
      />
      {props.hint && <p className="text-xs text-muted-foreground">{props.hint}</p>}
    </div>
  )
}

function RoleOption(props: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  title: string
  subtitle: string
}) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className={cn(
        'flex flex-col items-start gap-1 rounded-lg border p-3 text-left transition-colors',
        props.active
          ? 'border-primary bg-accent text-accent-foreground'
          : 'border-input hover:bg-muted',
      )}
      aria-pressed={props.active}
    >
      <span className="flex items-center gap-2 text-sm font-medium">
        {props.icon}
        {props.title}
      </span>
      <span className="text-xs text-muted-foreground">{props.subtitle}</span>
    </button>
  )
}

function SubmitButton({
  submitting,
  children,
}: {
  submitting: boolean
  children: React.ReactNode
}) {
  return (
    <Button type="submit" className="w-full" disabled={submitting}>
      {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </Button>
  )
}

/** "Continue with Google/GitHub" — rendered only for providers the backend has keys for.
 *  A full-page navigation (not fetch): the provider's consent screen must own the tab. */
function OAuthButtons({ providers, role }: { providers: OAuthProviderInfo[]; role: Role }) {
  if (providers.length === 0) return null
  return (
    <div className="mt-4 space-y-3">
      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-border" />
        <span className="text-xs uppercase tracking-wide text-muted-foreground">or</span>
        <div className="h-px flex-1 bg-border" />
      </div>
      <div className="grid gap-2">
        {providers.map((p) => (
          <Button
            key={p.name}
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => {
              window.location.href = api.oauthStartUrl(p.name, role)
            }}
          >
            <ProviderIcon name={p.name} />
            Continue with {providerLabel(p.name)}
          </Button>
        ))}
      </div>
    </div>
  )
}

function providerLabel(name: string): string {
  if (name === 'github') return 'GitHub'
  return name.charAt(0).toUpperCase() + name.slice(1)
}

function ProviderIcon({ name }: { name: string }) {
  if (name === 'google') {
    return (
      <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
        <path
          fill="#4285F4"
          d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1Z"
        />
        <path
          fill="#34A853"
          d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z"
        />
        <path
          fill="#FBBC05"
          d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84Z"
        />
        <path
          fill="#EA4335"
          d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15A11 11 0 0 0 2.18 7.06L5.84 9.9c.87-2.6 3.3-4.52 6.16-4.52Z"
        />
      </svg>
    )
  }
  if (name === 'github') {
    return (
      <svg className="h-4 w-4 fill-current" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 .3a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58l-.01-2.03c-3.34.72-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.74.08-.73.08-.73 1.2.09 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5 1 .1-.78.42-1.31.76-1.61-2.66-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.11-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6.01 0c2.29-1.55 3.29-1.23 3.29-1.23.66 1.66.25 2.88.12 3.18.77.84 1.24 1.91 1.24 3.22 0 4.61-2.81 5.63-5.49 5.92.43.37.82 1.11.82 2.23l-.01 3.3c0 .32.21.7.82.58A12 12 0 0 0 12 .3Z" />
      </svg>
    )
  }
  return null
}
