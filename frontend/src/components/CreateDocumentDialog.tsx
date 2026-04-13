import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'

interface Props {
  projectSlug: string
  onCreated: () => void
}

const DOC_TYPES = ['requirements', 'plan', 'decision', 'schema', 'brainstorm', 'session']

export function CreateDocumentDialog({ projectSlug, onCreated }: Props) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [docType, setDocType] = useState('plan')
  const [folder, setFolder] = useState('docs')
  const [saving, setSaving] = useState(false)
  const navigate = useNavigate()

  const filename = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') + '.md'
  const relativePath = `${folder}/${filename}`

  const handleSubmit = async () => {
    setSaving(true)
    try {
      const document = await api.documents.create(projectSlug, {
        relative_path: relativePath,
        title,
        doc_type: docType,
        content: `# ${title}\n\n`,
      })
      setOpen(false)
      setTitle('')
      onCreated()
      navigate({
        to: '/projects/$slug/docs/$',
        params: { slug: projectSlug, _splat: document.relative_path },
      })
    } catch (e) {
      alert(String(e))
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
    <div className="p-3 border rounded-lg bg-card space-y-2">
      <Input placeholder="Document title" value={title} onChange={(e) => setTitle(e.target.value)} />
      <select
        value={docType}
        onChange={(e) => setDocType(e.target.value)}
        className="w-full rounded border bg-background px-2 py-1.5 text-sm"
      >
        {DOC_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>
      <Input placeholder="Folder path" value={folder} onChange={(e) => setFolder(e.target.value)} className="text-xs font-mono" />
      <div className="text-xs text-muted-foreground font-mono">{relativePath}</div>
      <div className="flex gap-2">
        <Button size="sm" onClick={handleSubmit} disabled={!title || saving}>
          {saving ? 'Creating...' : 'Create'}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </div>
  )
}
