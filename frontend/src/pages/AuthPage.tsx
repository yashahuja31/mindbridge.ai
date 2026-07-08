/** Sign in / create account. On success we route back to where the user came from (or `/`). */

import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Briefcase, Loader2, UserRound, Users } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/context/AuthContext'
import { ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { Role } from '@/types'

export function AuthPage() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('hiree')
  const [submitting, setSubmitting] = useState(false)

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
