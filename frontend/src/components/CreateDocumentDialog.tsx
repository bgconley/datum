import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { DOCUMENT_TEMPLATES, getTemplate } from '@/lib/document-templates'

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
  const [templateId, setTemplateId] = useState('note')
  const [folder, setFolder] = useState('docs/notes')
  const [saving, setSaving] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const handleTemplateEvent = (event: Event) => {
      const detail = (event as CustomEvent<{ templateId?: string }>).detail
      const nextTemplateId = detail?.templateId ?? 'note'
      const template = getTemplate(nextTemplateId)
      setTemplateId(template.id)
      setFolder(template.folder)
      setOpen(true)
    }

    window.addEventListener(TEMPLATE_EVENT, handleTemplateEvent)
    return () => window.removeEventListener(TEMPLATE_EVENT, handleTemplateEvent)
  }, [])

  useEffect(() => {
    const template = getTemplate(templateId)
    setFolder(template.folder)
  }, [templateId])

  const template = useMemo(() => getTemplate(templateId), [templateId])
  const filename = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '') + '.md'
  const relativePath = `${folder.replace(/\/$/, '')}/${filename}`.replace(/^\/+/, '')

  const handleSubmit = async () => {
    setSaving(true)
    try {
      const document = await api.documents.create(projectSlug, {
        relative_path: relativePath,
        title,
        doc_type: template.docType,
        content: template.buildContent(title),
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
          {DOCUMENT_TEMPLATES.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
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
        <div className="font-medium text-foreground">{template.label}</div>
        <div className="mt-1 font-mono">{relativePath}</div>
      </div>

      <div className="flex gap-2">
        <Button size="sm" onClick={handleSubmit} disabled={!title || saving}>
          {saving ? 'Creating…' : 'Create'}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
