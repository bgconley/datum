import { useCallback, useRef, useState } from 'react'

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
          <span className="text-[14px] font-semibold text-white">Upload Document</span>
          <button
            type="button"
            onClick={close}
            className="text-[16px] text-white/80 hover:text-white"
          >
            {'\u2715'}
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-col gap-[20px] px-[28px] py-[24px]">
          {/* Drop zone */}
          <div
            className={`flex cursor-pointer flex-col items-center justify-center gap-[10px] rounded-[6px] border-2 border-dashed px-[20px] py-[32px] transition-colors ${
              dragging
                ? 'border-[#22a5f1] bg-[rgba(34,165,241,0.08)]'
                : file
                  ? 'border-[#22a5f1] bg-[#f3f6f8]'
                  : 'border-[#22a5f1] bg-[#f3f6f8]'
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
            {file ? (
              <>
                <span className="text-[13px] font-medium text-[#333]">{file.name}</span>
                <span className="text-[10px] text-[#666]">
                  {(file.size / 1024).toFixed(1)} KB &mdash; click or drag to replace
                </span>
              </>
            ) : (
              <>
                <span className="text-[28px]">{'\ud83d\udcc4'}</span>
                <span className="text-[13px] font-medium text-[#333]">
                  Drag files here or click to browse
                </span>
                <div className="flex items-center gap-[8px]">
                  {ACCEPTED_EXTENSIONS.map((ext) => (
                    <span
                      key={ext}
                      className="rounded-[3px] bg-[#e1e8ed] px-[6px] py-[2px] text-[9px] font-medium text-[#666]"
                    >
                      {ext}
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>

          <div className="h-px w-full bg-[#e1e8ed]" />

          {/* Destination folder */}
          <div className="flex flex-col gap-[8px]">
            <span className="text-[10px] font-semibold text-[#666]">DESTINATION FOLDER</span>
            <div className="flex items-center justify-between rounded-[4px] border border-[#e1e8ed] bg-white px-[12px] py-[10px]">
              <input
                type="text"
                value={folder}
                onChange={(e) => setFolder(e.target.value)}
                placeholder="docs/requirements/"
                className="min-w-0 flex-1 border-none bg-transparent text-[12px] text-[#333] outline-none"
              />
              <span className="shrink-0 rounded-[3px] border border-[#e1e8ed] bg-[#f3f6f8] px-[8px] py-[4px] text-[10px] font-medium text-[#333]">
                Browse {'\u25be'}
              </span>
            </div>
          </div>

          {/* Document type */}
          <div className="flex flex-col gap-[8px]">
            <span className="text-[10px] font-semibold text-[#666]">DOCUMENT TYPE</span>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="rounded-[4px] border border-[#e1e8ed] bg-white px-[12px] py-[10px] text-[12px] text-[#333] outline-none"
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
              onClick={handleUpload}
              disabled={!file || uploading}
              className="rounded-[4px] bg-[#22a5f1] px-[24px] py-[10px] text-[11px] font-semibold text-white disabled:opacity-40"
            >
              {uploading ? 'UPLOADING...' : 'UPLOAD'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
