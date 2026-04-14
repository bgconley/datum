import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
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
  const filename = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '') + '.md'
  const relativePath = `${folder.replace(/\/$/, '')}/${filename}`.replace(/^\/+/, '')

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
      setOpen(false)
      setTitle('')
      onCreated()
      navigate({
        to: '/projects/$slug/docs/$',
        params: { slug: projectSlug, _splat: document.relative_path },
      })
    } catch (error) {
      alert(String(error))
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return (
      <Button size="sm" variant="outline" className="w-full" onClick={() => setOpen(true)}>
        + New Document
      </Button>
    )
  }

  return (
    <div className="space-y-3 rounded-2xl border border-border/80 bg-card/80 p-4">
      <label className="space-y-1 text-sm">
        <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
          Template
        </span>
        <select
          value={templateId}
          onChange={(event) => setTemplateId(event.target.value)}
          className="w-full rounded-lg border border-input bg-background px-2 py-2 text-sm outline-none"
        >
          {templates.map((item) => (
            <option key={item.name} value={item.name}>
              {item.title}
            </option>
          ))}
        </select>
      </label>

      <Input
        placeholder="Document title"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
      />

      <label className="space-y-1 text-sm">
        <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
          Folder path
        </span>
        <Input
          placeholder="Folder path"
          value={folder}
          onChange={(event) => setFolder(event.target.value)}
          className="text-xs font-mono"
        />
      </label>

      <div className="rounded-xl border border-border/70 bg-background/70 px-3 py-2 text-xs text-muted-foreground">
        <div className="font-medium text-foreground">{template?.title ?? 'Template'}</div>
        <div className="mt-1 font-mono">{relativePath}</div>
        {template && <div className="mt-1">{template.description}</div>}
      </div>

      <div className="flex gap-2">
        <Button size="sm" onClick={handleSubmit} disabled={!title || saving || !template}>
          {saving ? 'Creating…' : 'Create'}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
