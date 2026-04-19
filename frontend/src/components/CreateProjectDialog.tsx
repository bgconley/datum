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
    // Fall back to raw error text.
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
  const [tags, setTags] = useState<string[]>([])
  const [tagDraft, setTagDraft] = useState('')
  const [slugTouched, setSlugTouched] = useState(Boolean(defaultName))
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) {
      setName(defaultName)
      setSlug(toProjectSlug(defaultName))
      setDescription('')
      setTags([])
      setTagDraft('')
      setSlugTouched(Boolean(defaultName))
      setError(null)
      setSaving(false)
      return
    }

    setName(defaultName)
    setSlug(toProjectSlug(defaultName))
    setDescription('')
    setTags([])
    setTagDraft('')
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

  const appendTag = (value: string) => {
    const normalized = value.trim().toLowerCase()
    if (!normalized || tags.includes(normalized)) {
      setTagDraft('')
      return
    }
    setTags((current) => [...current, normalized])
    setTagDraft('')
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
        tags,
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
        className="flex w-[370px] flex-col overflow-hidden rounded-[4px] border border-[#e1e8ed] bg-white shadow-[0px_8px_24px_0px_rgba(0,0,0,0.2)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between bg-[#22a5f1] px-[14px] py-[10px]">
          <div className="text-[14px] font-semibold text-white">Create Project</div>
          <button
            type="button"
            onClick={close}
            className="text-[16px] text-white/80 hover:text-white"
          >
            {'\u2715'}
          </button>
        </div>

        <div className="flex flex-col gap-[14px] px-[20px] py-[18px]">
          <div className="flex flex-col gap-[8px]">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">
              Project Name
            </span>
            <Input
              autoFocus
              placeholder="e.g. vendor-risk"
              value={name}
              onChange={(event) => handleNameChange(event.target.value)}
              className="h-[40px] rounded-[3px] border-[#d6e0e8] text-[12px]"
            />
          </div>

          <div className="flex flex-col gap-[8px]">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">
              Slug
            </span>
            <Input
              placeholder="vendor-risk"
              value={slug}
              onChange={(event) => handleSlugChange(event.target.value)}
              className="h-[40px] rounded-[3px] border-[#d6e0e8] font-mono text-[12px]"
            />
            {slugTouched && slugError ? (
              <div className="text-[11px] text-[#d9534f]">{slugError}</div>
            ) : null}
          </div>

          <div className="flex flex-col gap-[8px]">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">
              Description
            </span>
            <Textarea
              placeholder="Track vendor assessments, requirements, decisions, and open questions."
              value={description}
              onChange={(event) => {
                setDescription(event.target.value)
                if (error) {
                  setError(null)
                }
              }}
              rows={3}
              className="resize-none rounded-[3px] border-[#d6e0e8] text-[12px]"
            />
          </div>

          <div className="flex flex-col gap-[8px]">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">
              Optional Tags
            </span>
            <div className="flex flex-wrap items-center gap-2">
              {tags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  className="rounded-full bg-[#f3f6f8] px-[8px] py-[2px] text-[10px] font-medium text-[#1b2431]"
                  onClick={() => setTags((current) => current.filter((item) => item !== tag))}
                >
                  {tag}
                </button>
              ))}
              <input
                value={tagDraft}
                onChange={(event) => setTagDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ',') {
                    event.preventDefault()
                    appendTag(tagDraft)
                  }
                }}
                onBlur={() => appendTag(tagDraft)}
                placeholder="Add tag"
                className="h-6 min-w-[72px] border-0 bg-transparent p-0 text-[11px] text-[#7b8794] outline-none placeholder:text-[#999]"
              />
            </div>
          </div>

          {error && (
            <div className="rounded-[4px] border border-[#f1b4b4] bg-[#fff5f5] px-[12px] py-[10px] text-[12px] text-[#a94442]">
              {error}
            </div>
          )}

          <div className="border-t border-[#e1e8ed] pt-2 text-[11px] leading-5 text-[#7b8794]">
            Landing opens the new dashboard with Upload, Create Document, and Search.
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-[#e1e8ed] px-[20px] py-[10px]">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="border-[#d6e0e8] bg-white text-[#1b2431]"
            onClick={close}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            type="button"
            size="sm"
            className="bg-[#22a5f1] text-white hover:bg-[#1a94db]"
            disabled={!canSubmit}
            onClick={() => void handleSubmit()}
          >
            {saving ? 'Creating…' : 'Create Project'}
          </Button>
        </div>
      </div>
    </div>
  )
}
