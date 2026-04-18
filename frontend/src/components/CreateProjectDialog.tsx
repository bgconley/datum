import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/lib/api'
import { notify } from '@/lib/notifications'
import { recordProjectVisit } from '@/lib/project-preferences'
import { queryKeys } from '@/lib/query-keys'

export type ProjectCreationSource =
  | 'projects-home'
  | 'project-switcher'
  | 'command-palette'
  | 'unknown'

interface CreateProjectDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  source?: ProjectCreationSource
  defaultName?: string
}

const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]*$/

function toProjectSlug(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .replace(/--+/g, '-')
}

function validateSlug(slug: string) {
  if (!slug) {
    return 'Slug is required.'
  }
  if (!SLUG_PATTERN.test(slug)) {
    return 'Use lowercase letters, numbers, and hyphens only.'
  }
  if (slug.startsWith('-') || slug.endsWith('-') || slug.includes('--')) {
    return 'Slug cannot start, end, or repeat hyphens.'
  }
  return null
}

function getErrorMessage(error: unknown) {
  if (!(error instanceof Error)) {
    return 'Unable to create project.'
  }

  const [, rawBody = error.message] = error.message.split(': ', 2)
  try {
    const parsed = JSON.parse(rawBody) as { detail?: string }
    if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
      return parsed.detail
    }
  } catch {
    // Fall back to the raw message below.
  }

  return rawBody
}

export function CreateProjectDialog({
  open,
  onOpenChange,
  source = 'unknown',
  defaultName = '',
}: CreateProjectDialogProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [name, setName] = useState(defaultName)
  const [slug, setSlug] = useState(toProjectSlug(defaultName))
  const [description, setDescription] = useState('')
  const [slugTouched, setSlugTouched] = useState(Boolean(defaultName))
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) {
      setName(defaultName)
      setSlug(toProjectSlug(defaultName))
      setDescription('')
      setSlugTouched(Boolean(defaultName))
      setError(null)
      setSaving(false)
      return
    }

    setName(defaultName)
    setSlug(toProjectSlug(defaultName))
    setDescription('')
    setSlugTouched(Boolean(defaultName))
    setError(null)
  }, [defaultName, open])

  const slugError = useMemo(() => validateSlug(slug), [slug])
  const canSubmit = name.trim().length > 0 && !slugError && !saving

  const close = () => {
    if (saving) {
      return
    }
    onOpenChange(false)
  }

  const handleNameChange = (value: string) => {
    setName(value)
    if (!slugTouched) {
      setSlug(toProjectSlug(value))
    }
    if (error) {
      setError(null)
    }
  }

  const handleSlugChange = (value: string) => {
    setSlugTouched(true)
    setSlug(toProjectSlug(value))
    if (error) {
      setError(null)
    }
  }

  const handleSubmit = async () => {
    if (!canSubmit) {
      return
    }

    setSaving(true)
    setError(null)

    try {
      const project = await api.projects.create({
        name: name.trim(),
        slug,
        description: description.trim() || undefined,
      })

      await queryClient.invalidateQueries({ queryKey: queryKeys.projects })
      queryClient.setQueryData(queryKeys.project(project.slug), project)

      try {
        await queryClient.prefetchQuery({
          queryKey: queryKeys.workspace(project.slug),
          queryFn: () => api.projects.workspace(project.slug),
        })
      } catch (workspaceError) {
        notify(`Project created, but workspace preload failed: ${getErrorMessage(workspaceError)}`)
      }

      recordProjectVisit({
        slug: project.slug,
        pathname: `/projects/${project.slug}`,
        searchStr: '',
        section: 'dashboard',
        visitedAt: new Date().toISOString(),
      })

      onOpenChange(false)
      notify(`Project created from ${source.replace('-', ' ')}.`)
      navigate({
        to: '/projects/$slug',
        params: { slug: project.slug },
      })
    } catch (submitError) {
      setError(getErrorMessage(submitError))
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return null
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(27,36,49,0.5)]"
      onClick={close}
    >
      <div
        className="flex w-[520px] flex-col overflow-hidden rounded-[4px] border border-[#e1e8ed] bg-white shadow-[0px_8px_24px_0px_rgba(0,0,0,0.2)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between bg-[#22a5f1] px-[20px] py-[14px]">
          <div>
            <div className="text-[14px] font-semibold text-white">Create Project</div>
            <div className="mt-1 text-[10px] font-medium uppercase tracking-[0.16em] text-white/75">
              Workspace Setup
            </div>
          </div>
          <button
            type="button"
            onClick={close}
            className="text-[16px] text-white/80 hover:text-white"
          >
            {'\u2715'}
          </button>
        </div>

        <div className="flex flex-col gap-[18px] px-[28px] py-[24px]">
          <div className="flex flex-col gap-[8px]">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">
              Project Name
            </span>
            <Input
              autoFocus
              placeholder="Authentication Platform"
              value={name}
              onChange={(event) => handleNameChange(event.target.value)}
              className="h-[40px] border-[#d6e0e8] text-[13px]"
            />
          </div>

          <div className="flex flex-col gap-[8px]">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">
              Slug
            </span>
            <Input
              placeholder="authentication-platform"
              value={slug}
              onChange={(event) => handleSlugChange(event.target.value)}
              className="h-[40px] border-[#d6e0e8] font-mono text-[12px]"
            />
            <div className={`text-[11px] ${slugError ? 'text-[#d9534f]' : 'text-[#7b8794]'}`}>
              {slugError ?? 'Used in routes and on disk. Lowercase letters, numbers, hyphens.'}
            </div>
          </div>

          <div className="flex flex-col gap-[8px]">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">
              Description
            </span>
            <Textarea
              placeholder="Briefly describe the project focus or operational scope."
              value={description}
              onChange={(event) => {
                setDescription(event.target.value)
                if (error) {
                  setError(null)
                }
              }}
              rows={4}
              className="resize-none border-[#d6e0e8] text-[12px]"
            />
          </div>

          {error && (
            <div className="rounded-[4px] border border-[#f1b4b4] bg-[#fff5f5] px-[12px] py-[10px] text-[12px] text-[#a94442]">
              {error}
            </div>
          )}

          <div className="rounded-[4px] border border-[#e1e8ed] bg-[#f8fafb] px-[12px] py-[10px] text-[11px] leading-6 text-[#666]">
            New projects land on the dashboard onboarding state with quick actions for upload,
            document creation, and scoped search.
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[#e1e8ed] px-[28px] py-[16px]">
          <Button type="button" variant="ghost" onClick={close} disabled={saving}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="bg-[#22a5f1] text-white hover:bg-[#1a94db]"
          >
            {saving ? 'Creating…' : 'Create Project'}
          </Button>
        </div>
      </div>
    </div>
  )
}
