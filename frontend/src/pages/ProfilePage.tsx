/**
 * The signed-in user's persistent side of matching (M3):
 *   - hiree: one saved profile (resume + structured fields) + one-click "match from my profile".
 *   - hirer: saved job postings (CRUD) + one-click "match candidates" per posting.
 *
 * Both flows render results with the same shared components as the ad-hoc Match page. Skills and
 * experience are auto-extracted server-side when left blank — the form says so instead of
 * requiring them.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import {
  BadgeCheck,
  Briefcase,
  Loader2,
  Pencil,
  Plus,
  Search,
  Trash2,
  UserRound,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ControlsRow, Results, useMatchRunner } from '@/components/MatchControls'
import { useAuth } from '@/context/AuthContext'
import * as api from '@/lib/api'
import { ApiError } from '@/lib/api'
import type { Posting, PostingIn, Profile } from '@/types'

export function ProfilePage() {
  const { user } = useAuth()
  if (!user) return null // route is auth-gated; this is just for narrowing
  return user.role === 'hirer' ? <HirerPostings /> : <HireeProfile />
}

// ---- Hiree: one saved profile ---------------------------------------------------------------

function HireeProfile() {
  const { token } = useAuth()
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)

  const [k, setK] = useState(5)
  const [sources, setSources] = useState<string[]>(['sample'])
  const { results, running, run } = useMatchRunner()

  useEffect(() => {
    if (!token) return
    let cancelled = false
    api
      .getProfile(token)
      .then((p) => {
        if (!cancelled) setProfile(p)
      })
      .catch((err) => {
        // 404 = no profile yet; that's the empty state, not an error.
        if (!cancelled && err instanceof ApiError && err.status !== 404) {
          toast.error(err.message)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [token])

  async function save(form: ProfileFormValues) {
    if (!token) return
    setSaving(true)
    try {
      const saved = await api.putProfile(
        {
          name: form.name,
          headline: form.headline,
          // blank = let the server extract from the resume text
          skills: form.skills.trim()
            ? form.skills.split(',').map((s) => s.trim()).filter(Boolean)
            : null,
          years_experience: form.years.trim() ? Number(form.years) : null,
          location: form.location,
          open_to_remote: form.remote,
          desired_salary: form.salary.trim() ? Number(form.salary) : null,
          resume_text: form.resume,
        },
        token,
      )
      setProfile(saved)
      setEditing(false)
      toast.success('Profile saved')
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not save profile')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-24 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        Loading…
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center gap-3">
        <UserRound className="h-6 w-6 text-primary" />
        <h1 className="text-2xl font-bold tracking-tight">My profile</h1>
      </div>

      {!profile && !editing && (
        <div className="space-y-4 rounded-xl border border-dashed p-10 text-center">
          <p className="text-muted-foreground">
            No profile yet. Save one and matching becomes one click — no re-pasting your resume.
          </p>
          <Button onClick={() => setEditing(true)}>
            <Plus className="h-4 w-4" />
            Create profile
          </Button>
        </div>
      )}

      {editing && (
        <ProfileForm
          initial={profile}
          saving={saving}
          onSave={save}
          onCancel={() => setEditing(false)}
        />
      )}

      {profile && !editing && (
        <>
          <Card>
            <CardHeader className="flex-row items-start justify-between gap-4 space-y-0">
              <div className="min-w-0 space-y-1">
                <CardTitle className="text-lg">
                  {profile.name || 'Unnamed'}
                  {profile.headline && (
                    <span className="ml-2 font-normal text-muted-foreground">
                      · {profile.headline}
                    </span>
                  )}
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  {profile.years_experience > 0 && `${profile.years_experience}y experience`}
                  {profile.location && ` · ${profile.location}`}
                  {profile.open_to_remote && ' · open to remote'}
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                <Pencil className="h-4 w-4" />
                Edit
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {profile.skills.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {profile.skills.map((s) => (
                    <Badge key={s} variant="secondary">
                      {s}
                    </Badge>
                  ))}
                </div>
              )}
              {profile.resume_text && (
                <p className="line-clamp-3 whitespace-pre-line text-sm text-muted-foreground">
                  {profile.resume_text}
                </p>
              )}

              <div className="space-y-4 border-t pt-4">
                <ControlsRow
                  k={k}
                  setK={setK}
                  sources={sources}
                  setSources={setSources}
                  disabled={running}
                />
                <Button
                  onClick={() =>
                    void run(
                      () => api.matchFromProfile(k, sources.length ? sources : null, token!),
                      true,
                    )
                  }
                  disabled={running}
                  className="w-full sm:w-auto"
                >
                  {running ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                  Match jobs to my profile
                </Button>
              </div>
            </CardContent>
          </Card>

          <Results results={results} noun="jobs" running={running} />
        </>
      )}
    </div>
  )
}

interface ProfileFormValues {
  name: string
  headline: string
  skills: string
  years: string
  location: string
  remote: boolean
  salary: string
  resume: string
}

function ProfileForm({
  initial,
  saving,
  onSave,
  onCancel,
}: {
  initial: Profile | null
  saving: boolean
  onSave: (v: ProfileFormValues) => void
  onCancel: () => void
}) {
  const [v, setV] = useState<ProfileFormValues>({
    name: initial?.name ?? '',
    headline: initial?.headline ?? '',
    skills: initial?.skills.join(', ') ?? '',
    years: initial && initial.years_experience > 0 ? String(initial.years_experience) : '',
    location: initial?.location ?? '',
    remote: initial?.open_to_remote ?? true,
    salary: initial?.desired_salary != null ? String(initial.desired_salary) : '',
    resume: initial?.resume_text ?? '',
  })
  const set = <K extends keyof ProfileFormValues>(key: K, val: ProfileFormValues[K]) =>
    setV((prev) => ({ ...prev, [key]: val }))

  function submit(e: FormEvent) {
    e.preventDefault()
    onSave(v)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{initial ? 'Edit profile' : 'Create profile'}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="pf-name">Name</Label>
              <Input
                id="pf-name"
                value={v.name}
                onChange={(e) => set('name', e.target.value)}
                placeholder="Ada Lovelace"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pf-headline">Headline</Label>
              <Input
                id="pf-headline"
                value={v.headline}
                onChange={(e) => set('headline', e.target.value)}
                placeholder="Senior Backend Engineer"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="pf-resume">Resume text</Label>
            <Textarea
              id="pf-resume"
              rows={7}
              value={v.resume}
              onChange={(e) => set('resume', e.target.value)}
              placeholder="Paste your resume — skills and experience are extracted automatically."
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="pf-skills">
              Skills{' '}
              <span className="font-normal text-muted-foreground">
                (comma-separated; leave blank to auto-extract from the resume)
              </span>
            </Label>
            <Input
              id="pf-skills"
              value={v.skills}
              onChange={(e) => set('skills', e.target.value)}
              placeholder="python, fastapi, postgresql"
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="pf-years">
                Years exp.{' '}
                <span className="font-normal text-muted-foreground">(blank = auto)</span>
              </Label>
              <Input
                id="pf-years"
                type="number"
                min={0}
                max={60}
                step={0.5}
                value={v.years}
                onChange={(e) => set('years', e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pf-location">Location</Label>
              <Input
                id="pf-location"
                value={v.location}
                onChange={(e) => set('location', e.target.value)}
                placeholder="Mumbai"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pf-salary">Desired salary</Label>
              <Input
                id="pf-salary"
                type="number"
                min={0}
                value={v.salary}
                onChange={(e) => set('salary', e.target.value)}
                placeholder="90000"
              />
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={v.remote}
              onChange={(e) => set('remote', e.target.checked)}
              className="h-4 w-4 rounded border-input accent-primary"
            />
            Open to remote work
          </label>

          <div className="flex gap-2">
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <BadgeCheck className="h-4 w-4" />}
              Save profile
            </Button>
            <Button type="button" variant="ghost" onClick={onCancel} disabled={saving}>
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

// ---- Hirer: saved postings ------------------------------------------------------------------

function HirerPostings() {
  const { token } = useAuth()
  const [postings, setPostings] = useState<Posting[] | null>(null)
  const [editing, setEditing] = useState<Posting | 'new' | null>(null)
  const [saving, setSaving] = useState(false)
  const [matchingId, setMatchingId] = useState<number | null>(null)

  const [k, setK] = useState(5)
  const [sources, setSources] = useState<string[]>(['sample'])
  const { results, running, run } = useMatchRunner()

  useEffect(() => {
    if (!token) return
    let cancelled = false
    api
      .listPostings(token)
      .then((rows) => {
        if (!cancelled) setPostings(rows)
      })
      .catch((err) => {
        if (!cancelled) toast.error(err instanceof ApiError ? err.message : 'Could not load postings')
      })
    return () => {
      cancelled = true
    }
  }, [token])

  async function save(data: PostingIn) {
    if (!token) return
    setSaving(true)
    try {
      if (editing && editing !== 'new') {
        const updated = await api.updatePosting(editing.id, data, token)
        setPostings((rows) => rows?.map((p) => (p.id === updated.id ? updated : p)) ?? null)
      } else {
        const created = await api.createPosting(data, token)
        setPostings((rows) => [created, ...(rows ?? [])])
      }
      setEditing(null)
      toast.success('Posting saved')
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not save posting')
    } finally {
      setSaving(false)
    }
  }

  async function remove(p: Posting) {
    if (!token) return
    try {
      await api.deletePosting(p.id, token)
      setPostings((rows) => rows?.filter((x) => x.id !== p.id) ?? null)
      toast.success(`Deleted "${p.title}"`)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not delete posting')
    }
  }

  function matchPosting(p: Posting) {
    setMatchingId(p.id)
    void run(() => api.matchFromPosting(p.id, k, sources.length ? sources : null, token!), true)
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Briefcase className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold tracking-tight">My postings</h1>
        </div>
        {editing === null && (
          <Button size="sm" onClick={() => setEditing('new')}>
            <Plus className="h-4 w-4" />
            New posting
          </Button>
        )}
      </div>

      {editing !== null && (
        <PostingForm
          initial={editing === 'new' ? null : editing}
          saving={saving}
          onSave={save}
          onCancel={() => setEditing(null)}
        />
      )}

      {postings === null ? (
        <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading…
        </div>
      ) : postings.length === 0 && editing === null ? (
        <div className="space-y-4 rounded-xl border border-dashed p-10 text-center">
          <p className="text-muted-foreground">
            No saved postings yet. Save the roles you're hiring for and match candidates in one
            click.
          </p>
          <Button onClick={() => setEditing('new')}>
            <Plus className="h-4 w-4" />
            Create posting
          </Button>
        </div>
      ) : (
        postings.length > 0 && (
          <>
            <ControlsRow
              k={k}
              setK={setK}
              sources={sources}
              setSources={setSources}
              disabled={running}
            />
            <div className="space-y-3">
              {postings.map((p) => (
                <Card key={p.id}>
                  <CardHeader className="flex-row items-start justify-between gap-4 space-y-0">
                    <div className="min-w-0 space-y-1">
                      <CardTitle className="text-base">
                        {p.title}
                        {p.company && (
                          <span className="ml-2 font-normal text-muted-foreground">
                            · {p.company}
                          </span>
                        )}
                      </CardTitle>
                      <div className="flex flex-wrap gap-1.5">
                        {p.skills.slice(0, 8).map((s) => (
                          <Badge key={s} variant="muted">
                            {s}
                          </Badge>
                        ))}
                        {p.remote && <Badge variant="secondary">remote</Badge>}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      <Button
                        size="sm"
                        onClick={() => matchPosting(p)}
                        disabled={running}
                        aria-label={`Match candidates for ${p.title}`}
                      >
                        {running && matchingId === p.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Search className="h-4 w-4" />
                        )}
                        Match
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setEditing(p)}
                        aria-label={`Edit ${p.title}`}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => void remove(p)}
                        aria-label={`Delete ${p.title}`}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </CardHeader>
                </Card>
              ))}
            </div>

            <Results results={results} noun="candidates" running={running} />
          </>
        )
      )}
    </div>
  )
}

function PostingForm({
  initial,
  saving,
  onSave,
  onCancel,
}: {
  initial: Posting | null
  saving: boolean
  onSave: (data: PostingIn) => void
  onCancel: () => void
}) {
  const [title, setTitle] = useState(initial?.title ?? '')
  const [company, setCompany] = useState(initial?.company ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [skills, setSkills] = useState(initial?.skills.join(', ') ?? '')
  const [location, setLocation] = useState(initial?.location ?? '')
  const [remote, setRemote] = useState(initial?.remote ?? false)
  const [applyUrl, setApplyUrl] = useState(initial?.apply_url ?? '')

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) {
      toast.error('A job title is required')
      return
    }
    onSave({
      title: title.trim(),
      company,
      description,
      skills: skills.trim() ? skills.split(',').map((s) => s.trim()).filter(Boolean) : null,
      location,
      remote,
      apply_url: applyUrl.trim() || undefined,
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{initial ? 'Edit posting' : 'New posting'}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="po-title">Job title</Label>
              <Input
                id="po-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Machine Learning Engineer"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="po-company">Company</Label>
              <Input
                id="po-company"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Acme Corp"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="po-desc">Job description</Label>
            <Textarea
              id="po-desc"
              rows={6}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What the role involves — skills are extracted automatically."
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="po-skills">
                Skills{' '}
                <span className="font-normal text-muted-foreground">(blank = auto-extract)</span>
              </Label>
              <Input
                id="po-skills"
                value={skills}
                onChange={(e) => setSkills(e.target.value)}
                placeholder="python, pytorch, nlp"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="po-location">Location</Label>
              <Input
                id="po-location"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Bengaluru"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="po-apply">Application Link / Career URL</Label>
            <Input
              id="po-apply"
              type="url"
              value={applyUrl}
              onChange={(e) => setApplyUrl(e.target.value)}
              placeholder="https://company.com/careers/apply-job-123"
            />
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={remote}
              onChange={(e) => setRemote(e.target.checked)}
              className="h-4 w-4 rounded border-input accent-primary"
            />
            Remote-friendly
          </label>

          <div className="flex gap-2">
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <BadgeCheck className="h-4 w-4" />}
              Save posting
            </Button>
            <Button type="button" variant="ghost" onClick={onCancel} disabled={saving}>
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
