import { useCallback, useRef, useState } from 'react'
import { FileUp, X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { notify } from '@/lib/notifications'

interface UploadModalProps {
  projectSlug: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

const ACCEPTED_EXTENSIONS = ['.md', '.sql', '.yaml', '.yml', '.txt', '.pdf', '.docx']
const ACCEPTED_MIME =
  '.md,.sql,.yaml,.yml,.txt,.pdf,.docx,text/markdown,text/plain,text/x-sql,text/yaml,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document'

export function UploadModal({ projectSlug, open, onOpenChange, onSuccess }: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null)
  const [folder, setFolder] = useState('docs/requirements/')
  const [docType, setDocType] = useState('')
  const [tagInput, setTagInput] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const reset = () => {
    setFile(null)
    setFolder('docs/requirements/')
    setDocType('')
    setTagInput('')
    setTags([])
    setUploading(false)
    setDragging(false)
  }

  const close = () => {
    reset()
    onOpenChange(false)
  }

  const isAcceptedFile = (f: File) => {
    const ext = '.' + f.name.split('.').pop()?.toLowerCase()
    return ACCEPTED_EXTENSIONS.includes(ext)
  }

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return
    const f = files[0]
    if (!isAcceptedFile(f)) {
      notify('Unsupported file type. Accepted: ' + ACCEPTED_EXTENSIONS.join(', '))
      return
    }
    setFile(f)
  }

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragging(false)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setDragging(false)
      handleFiles(e.dataTransfer.files)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

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

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    try {
      await api.ingest.upload(
        projectSlug,
        file,
        folder,
        docType || undefined,
        tags.length > 0 ? tags.join(',') : undefined,
      )
      notify('Document uploaded successfully')
      close()
      onSuccess?.()
    } catch (error) {
      notify(String(error))
    } finally {
      setUploading(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20" onClick={close}>
      <div
        className="w-full max-w-lg rounded bg-white shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between rounded-t bg-primary px-6 py-3">
          <span className="text-sm font-semibold text-white">Upload Document</span>
          <button type="button" onClick={close} className="text-white/80 hover:text-white">
            <X className="size-4" />
          </button>
        </div>

        {/* Body */}
        <div className="space-y-5 p-6">
          {/* Drag-drop zone */}
          <div
            className={`flex cursor-pointer flex-col items-center justify-center rounded border-2 border-dashed px-6 py-8 transition-colors ${
              dragging
                ? 'border-primary bg-primary/5'
                : file
                  ? 'border-primary/40 bg-primary/5'
                  : 'border-primary/30 hover:border-primary/60'
            }`}
            onDragOver={handleDragOver}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept={ACCEPTED_MIME}
              onChange={(e) => handleFiles(e.target.files)}
            />
            <FileUp className="mb-2 size-8 text-primary/60" />
            {file ? (
              <div className="text-center">
                <div className="text-sm font-medium text-foreground">{file.name}</div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {(file.size / 1024).toFixed(1)} KB — click or drag to replace
                </div>
              </div>
            ) : (
              <>
                <div className="text-sm text-muted-foreground">
                  Drag files here or click to browse
                </div>
                <div className="mt-2 flex flex-wrap justify-center gap-1.5">
                  {ACCEPTED_EXTENSIONS.map((ext) => (
                    <Badge key={ext} variant="secondary" className="text-[10px]">
                      {ext}
                    </Badge>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Destination folder */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
              Destination folder
            </label>
            <input
              type="text"
              value={folder}
              onChange={(e) => setFolder(e.target.value)}
              placeholder="docs/requirements/"
              className="w-full rounded border border-border bg-white px-3 py-2 text-sm"
            />
          </div>

          {/* Document type */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
              Document type
            </label>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="w-full rounded border border-border bg-white px-3 py-2 text-sm outline-none"
            >
              <option value="">Auto-detect from extension</option>
              <option value="requirement">Requirement</option>
              <option value="architecture">Architecture</option>
              <option value="schema">Schema</option>
              <option value="session-note">Session Note</option>
              <option value="reference">Reference</option>
            </select>
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
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 border-t border-border px-6 py-4">
          <Button variant="outline" onClick={close}>
            Cancel
          </Button>
          <Button onClick={handleUpload} disabled={!file || uploading}>
            {uploading ? 'Uploading...' : 'Upload'}
          </Button>
        </div>
      </div>
    </div>
  )
}
