import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'

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
    if (!template) return
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

  // Sidebar trigger button (always rendered)
  const triggerButton = (
    <button
      type="button"
      className="w-full py-[5px] pl-4 pr-3 text-left text-[11px] font-medium text-[#22a5f1] hover:text-[#22a5f1]/80"
      onClick={() => setOpen(true)}
    >
      + New Document
    </button>
  )

  if (!open) return triggerButton

  return (
    <>
      {triggerButton}

      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(27,36,49,0.5)]"
        onClick={close}
      >
        <div
          className="flex w-[520px] flex-col overflow-hidden rounded-[4px] border border-[#e1e8ed] bg-white shadow-[0px_8px_24px_0px_rgba(0,0,0,0.2)]"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between bg-[#22a5f1] px-[20px] py-[14px]">
            <span className="text-[14px] font-semibold text-white">Create Document</span>
            <button
              type="button"
              onClick={close}
              className="text-[16px] text-white/80 hover:text-white"
            >
              {'\u2715'}
            </button>
          </div>

          {/* Body */}
          <div className="flex flex-col gap-[20px] overflow-auto px-[28px] py-[24px]">
            {/* Template */}
            <div className="flex flex-col gap-[8px]">
              <span className="text-[10px] font-semibold text-[#666]">TEMPLATE</span>
              <select
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                className="rounded-[4px] border border-[#22a5f1] bg-white px-[12px] py-[10px] text-[12px] font-medium text-[#333] outline-none"
              >
                {templates.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.title}
                  </option>
                ))}
              </select>
              <div className="flex flex-wrap gap-x-[8px] gap-y-[0px]">
                {templates.map((item) => (
                  <button
                    key={item.name}
                    type="button"
                    onClick={() => setTemplateId(item.name)}
                    className={`rounded-[4px] border px-[12px] py-[6px] text-[11px] ${
                      item.name === templateId
                        ? 'border-[#22a5f1] bg-[#22a5f1] font-semibold text-white'
                        : 'border-[#e1e8ed] bg-white text-[#333]'
                    }`}
                  >
                    {item.title}
                  </button>
                ))}
              </div>
            </div>

            <div className="h-px w-full bg-[#e1e8ed]" />

            {/* Title */}
            <div className="flex flex-col gap-[8px]">
              <span className="text-[10px] font-semibold text-[#666]">TITLE</span>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Document title"
                className="rounded-[4px] border border-[#e1e8ed] bg-white px-[12px] py-[10px] text-[12px] text-[#333] outline-none"
              />
            </div>

            {/* Folder path */}
            <div className="flex flex-col gap-[8px]">
              <span className="text-[10px] font-semibold text-[#666]">FOLDER PATH</span>
              <div className="flex items-center justify-between rounded-[4px] border border-[#e1e8ed] bg-white px-[12px] py-[10px]">
                <input
                  type="text"
                  value={folder}
                  onChange={(e) => setFolder(e.target.value)}
                  placeholder="docs/decisions/"
                  className="min-w-0 flex-1 border-none bg-transparent text-[12px] text-[#333] outline-none"
                />
                <span className="shrink-0 rounded-[3px] border border-[#e1e8ed] bg-[#f3f6f8] px-[8px] py-[4px] text-[10px] font-medium text-[#333]">
                  Browse {'\u25be'}
                </span>
              </div>
            </div>

            {/* Preview */}
            <div className="flex items-center gap-[8px]">
              <span className="text-[10px] text-[#666]">Preview:</span>
              <span className="font-mono text-[11px] text-[#22a5f1]">{relativePath}</span>
            </div>

            <div className="h-px w-full bg-[#e1e8ed]" />

            {/* Tags */}
            <div className="flex flex-col gap-[8px]">
              <span className="text-[10px] font-semibold text-[#666]">TAGS</span>
              <div className="flex flex-wrap items-center gap-[8px] rounded-[4px] border border-[#e1e8ed] bg-white px-[12px] py-[8px]">
                {tags.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => removeTag(tag)}
                    className="rounded-[3px] bg-[rgba(34,165,241,0.1)] px-[8px] py-[3px] text-[10px] font-medium text-[#22a5f1] hover:bg-[rgba(34,165,241,0.2)]"
                  >
                    {tag}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => {
                    const value = window.prompt('Add tag')
                    if (value?.trim() && !tags.includes(value.trim())) {
                      setTags((prev) => [...prev, value.trim()])
                    }
                  }}
                  className="rounded-[3px] border border-[#e1e8ed] px-[6px] py-[3px] text-[10px] font-medium text-[#666]"
                >
                  +
                </button>
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={handleTagKeyDown}
                  placeholder={tags.length === 0 ? 'Type and press Enter...' : ''}
                  className="min-w-[80px] flex-1 border-none bg-transparent text-[10px] outline-none"
                />
              </div>
            </div>

            <div className="h-px w-full bg-[#e1e8ed]" />

            {/* Footer */}
            <div className="flex items-start justify-end gap-[12px]">
              <button
                type="button"
                onClick={close}
                className="rounded-[4px] border border-[#e1e8ed] bg-white px-[20px] py-[10px] text-[11px] font-semibold text-[#333]"
              >
                CANCEL
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={!title || saving || !template}
                className="rounded-[4px] bg-[#22a5f1] px-[24px] py-[10px] text-[11px] font-semibold text-white disabled:opacity-40"
              >
                {saving ? 'CREATING...' : 'CREATE & EDIT'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
