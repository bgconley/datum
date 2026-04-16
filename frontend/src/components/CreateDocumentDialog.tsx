import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { notify } from '@/lib/notifications'
import { queryKeys } from '@/lib/query-keys'

interface Props {
  projectSlug: string
  onCreated: () => void
}

const TEMPLATE_EVENT = 'datum:new-document-template'

export function openTemplateDialog(templateId: string) {
  window.dispatchEvent(new CustomEvent(TEMPLATE_EVENT, { detail: { templateId } }))
}

export function CreateDocumentDialog({ projectSlug, onCreated }: Props) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [templateId, setTemplateId] = useState('adr')
  const [folder, setFolder] = useState('docs/decisions')
  const [tagInput, setTagInput] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const navigate = useNavigate()
  const templatesQuery = useQuery({
    queryKey: queryKeys.templates,
    queryFn: api.templates.list,
  })
  const templates = templatesQuery.data ?? []

  useEffect(() => {
    const handleTemplateEvent = (event: Event) => {
      const detail = (event as CustomEvent<{ templateId?: string }>).detail
      const nextTemplateId = detail?.templateId ?? 'adr'
      const template = templates.find((item) => item.name === nextTemplateId) ?? templates[0]
      if (template) {
        setTemplateId(template.name)
        setFolder(template.default_folder)
      }
      setOpen(true)
    }

    window.addEventListener(TEMPLATE_EVENT, handleTemplateEvent)
    return () => window.removeEventListener(TEMPLATE_EVENT, handleTemplateEvent)
  }, [templates])

  useEffect(() => {
    const template = templates.find((item) => item.name === templateId)
    if (template) {
      setFolder(template.default_folder)
    }
  }, [templateId, templates])

  const template = useMemo(
    () => templates.find((item) => item.name === templateId) ?? templates[0] ?? null,
    [templateId, templates],
  )
  const filename =
    title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '') + '.md'
  const relativePath = `${folder.replace(/\/$/, '')}/${filename}`.replace(/^\/+/, '')

  const close = () => {
    setOpen(false)
    setTitle('')
    setTagInput('')
    setTags([])
  }

  const handleTagKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if ((e.key === 'Enter' || e.key === ',') && tagInput.trim()) {
      e.preventDefault()
      const value = tagInput.trim().replace(/,$/g, '')
      if (value && !tags.includes(value)) {
        setTags((prev) => [...prev, value])
      }
      setTagInput('')
    } else if (e.key === 'Backspace' && !tagInput && tags.length > 0) {
      setTags((prev) => prev.slice(0, -1))
    }
  }

  const removeTag = (tag: string) => {
    setTags((prev) => prev.filter((t) => t !== tag))
  }

  const handleSubmit = async () => {
    if (!template) {
      return
    }
    setSaving(true)
    try {
      const rendered = await api.templates.render(templateId, title)
      const document = await api.documents.create(projectSlug, {
        relative_path: relativePath,
        title,
        doc_type: rendered.doc_type,
        content: rendered.content,
      })
      close()
      onCreated()
      navigate({
        to: '/projects/$slug/docs/$',
        params: { slug: projectSlug, _splat: document.relative_path },
      })
    } catch (error) {
      notify(String(error))
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        className="w-full py-[5px] pl-4 pr-3 text-left text-[11px] font-medium text-[#22a5f1] hover:text-[#22a5f1]/80"
        onClick={() => setOpen(true)}
      >
        + New Document
      </button>
    )
  }

  return (
    <>
      {/* Trigger button stays in the sidebar */}
      <button
        type="button"
        className="w-full py-[5px] pl-4 pr-3 text-left text-[11px] font-medium text-[#22a5f1] hover:text-[#22a5f1]/80"
        onClick={() => setOpen(true)}
      >
        + New Document
      </button>

      {/* Modal overlay rendered via portal-like fixed positioning */}
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20" onClick={close}>
        <div
          className="w-full max-w-lg rounded bg-white shadow-lg"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between rounded-t bg-primary px-6 py-3">
            <span className="text-sm font-semibold text-white">Create Document</span>
            <button type="button" onClick={close} className="text-white/80 hover:text-white">
              <X className="size-4" />
            </button>
          </div>

          {/* Body */}
          <div className="space-y-5 p-6">
            {/* Template selector */}
            <div className="space-y-1.5">
              <label className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Template
              </label>
              <select
                value={templateId}
                onChange={(event) => setTemplateId(event.target.value)}
                className="w-full rounded border border-border bg-white px-3 py-2 text-sm outline-none"
              >
                {templates.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.title}
                  </option>
                ))}
              </select>
              {/* Template chip grid */}
              <div className="flex flex-wrap gap-1.5 pt-1">
                {templates.map((item) => (
                  <Badge
                    key={item.name}
                    variant={item.name === templateId ? 'default' : 'secondary'}
                    className="cursor-pointer text-xs"
                    onClick={() => setTemplateId(item.name)}
                  >
                    {item.title}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Title */}
            <div className="space-y-1.5">
              <label className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Document title"
                className="w-full rounded border border-border bg-white px-3 py-2 text-sm"
              />
            </div>

            {/* Folder path */}
            <div className="space-y-1.5">
              <label className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Folder path
              </label>
              <input
                type="text"
                value={folder}
                onChange={(event) => setFolder(event.target.value)}
                placeholder="docs/decisions/"
                className="w-full rounded border border-border bg-white px-3 py-2 font-mono text-sm"
              />
            </div>

            {/* Tags */}
            <div className="space-y-1.5">
              <label className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Tags
              </label>
              <div className="flex flex-wrap items-center gap-1.5 rounded border border-border bg-white px-3 py-2">
                {tags.map((tag) => (
                  <Badge key={tag} variant="secondary" className="gap-1 text-xs">
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(tag)}
                      className="ml-0.5 hover:text-destructive"
                    >
                      <X className="size-3" />
                    </button>
                  </Badge>
                ))}
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={handleTagKeyDown}
                  placeholder={tags.length === 0 ? 'Add tags...' : ''}
                  className="min-w-[80px] flex-1 border-none bg-transparent text-sm outline-none"
                />
              </div>
            </div>

            {/* Preview path */}
            <div className="rounded border border-border/70 bg-background/70 px-3 py-2 text-xs text-muted-foreground">
              <div className="font-medium text-foreground">{template?.title ?? 'Template'}</div>
              <div className="mt-1 font-mono">{relativePath}</div>
              {template && <div className="mt-1">{template.description}</div>}
            </div>
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-3 border-t border-border px-6 py-4">
            <Button variant="outline" onClick={close}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={!title || saving || !template}>
              {saving ? 'Creating...' : 'Create & Edit'}
            </Button>
          </div>
        </div>
      </div>
    </>
  )
}
