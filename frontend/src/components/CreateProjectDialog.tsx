import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/lib/api'
import { notify } from '@/lib/notifications'

interface Props {
  onCreated: () => void
}

export function CreateProjectDialog({ onCreated }: Props) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const navigate = useNavigate()

  const handleNameChange = (v: string) => {
    setName(v)
    setSlug(v.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''))
  }

  const handleSubmit = async () => {
    setSaving(true)
    try {
      const project = await api.projects.create({
        name,
        slug,
        description: description || undefined,
      })
      setOpen(false)
      setName('')
      setSlug('')
      setDescription('')
      onCreated()
      navigate({ to: '/projects/$slug', params: { slug: project.slug } })
    } catch (e) {
      notify(String(e))
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return (
      <Button size="sm" variant="outline" className="w-full" onClick={() => setOpen(true)}>
        + New Project
      </Button>
    )
  }

  return (
    <div className="p-3 border rounded-lg bg-card space-y-2">
      <Input placeholder="Project name" value={name} onChange={(e) => handleNameChange(e.target.value)} />
      <Input placeholder="slug" value={slug} onChange={(e) => setSlug(e.target.value)} className="text-xs font-mono" />
      <Textarea placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
      <div className="flex gap-2">
        <Button size="sm" onClick={handleSubmit} disabled={!name || !slug || saving}>
          {saving ? 'Creating...' : 'Create'}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </div>
  )
}
