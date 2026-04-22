import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { api } from '@/lib/api'
import { notify } from '@/lib/notifications'
import {
  collectProjectDocumentFolders,
  CUSTOM_FOLDER_VALUE,
  formatDocumentFolderLabel,
  normalizeDocumentFolderPath,
} from '@/lib/project-folders'
import { useProjectWorkspaceQuery } from '@/lib/workspace-query'

interface UploadModalProps {
  projectSlug: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

const ACCEPTED_EXTENSIONS = ['.md', '.sql', '.yaml', '.yml', '.txt', '.pdf', '.docx']
const ACCEPTED_MIME =
  '.md,.sql,.yaml,.yml,.txt,.pdf,.docx,text/markdown,text/plain,text/x-sql,text/yaml,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const DOC_TYPE_OPTIONS = [
  { value: '', label: 'Auto-detect from extension' },
  { value: 'requirements', label: 'Requirements' },
  { value: 'decision', label: 'Decision / ADR' },
  { value: 'plan', label: 'Plan' },
  { value: 'session', label: 'Session' },
  { value: 'schema', label: 'Schema' },
  { value: 'config', label: 'Config' },
  { value: 'reference', label: 'Reference' },
  { value: 'note', label: 'Note' },
]
const DEFAULT_FOLDER_BY_DOC_TYPE: Record<string, string> = {
  requirements: 'docs/requirements',
  decision: 'docs/decisions',
  plan: 'docs/plans',
  session: 'docs/sessions',
  schema: 'docs/schema',
  config: 'docs/config',
  reference: 'docs/reference',
  note: 'docs/notes',
}

export function UploadModal({ projectSlug, open, onOpenChange, onSuccess }: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null)
  const [folder, setFolder] = useState('docs/requirements')
  const [folderTouched, setFolderTouched] = useState(false)
  const [useCustomFolder, setUseCustomFolder] = useState(false)
  const [docType, setDocType] = useState('')
  const [tagInput, setTagInput] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const workspaceQuery = useProjectWorkspaceQuery(projectSlug)
  const documents = workspaceQuery.data?.documents ?? []
  const folderOptions = useMemo(
    () =>
      collectProjectDocumentFolders(
        documents,
        Object.values(DEFAULT_FOLDER_BY_DOC_TYPE),
      ),
    [documents],
  )
  const normalizedFolder = normalizeDocumentFolderPath(folder)
  const folderSelectValue =
    useCustomFolder || !folderOptions.includes(normalizedFolder)
      ? CUSTOM_FOLDER_VALUE
      : normalizedFolder

  useEffect(() => {
    if (folderTouched || !docType) {
      return
    }
    const suggestedFolder = DEFAULT_FOLDER_BY_DOC_TYPE[docType]
    if (suggestedFolder) {
      setFolder(suggestedFolder)
      setUseCustomFolder(false)
    }
  }, [docType, folderTouched])

  const reset = () => {
    setFile(null)
    setFolder('docs/requirements')
    setFolderTouched(false)
    setUseCustomFolder(false)
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
        normalizedFolder,
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
            <select
              value={folderSelectValue}
              onChange={(e) => {
                const nextValue = e.target.value
                setFolderTouched(true)
                if (nextValue === CUSTOM_FOLDER_VALUE) {
                  setUseCustomFolder(true)
                  return
                }
                setUseCustomFolder(false)
                setFolder(nextValue)
              }}
              className="rounded-[4px] border border-[#e1e8ed] bg-white px-[12px] py-[10px] text-[12px] text-[#333] outline-none"
            >
              {folderOptions.map((option) => (
                <option key={option} value={option}>
                  {formatDocumentFolderLabel(option)}
                </option>
              ))}
              <option value={CUSTOM_FOLDER_VALUE}>Custom path...</option>
            </select>
            {folderSelectValue === CUSTOM_FOLDER_VALUE && (
              <input
                type="text"
                value={folder}
                onChange={(e) => {
                  setFolderTouched(true)
                  setUseCustomFolder(true)
                  setFolder(e.target.value)
                }}
                placeholder="docs/requirements"
                className="rounded-[4px] border border-[#e1e8ed] bg-white px-[12px] py-[10px] text-[12px] text-[#333] outline-none"
              />
            )}
          </div>

          {/* Document type */}
          <div className="flex flex-col gap-[8px]">
            <span className="text-[10px] font-semibold text-[#666]">DOCUMENT TYPE</span>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="rounded-[4px] border border-[#e1e8ed] bg-white px-[12px] py-[10px] text-[12px] text-[#333] outline-none"
            >
              {DOC_TYPE_OPTIONS.map((option) => (
                <option key={option.value || 'auto'} value={option.value}>
                  {option.label}
                </option>
              ))}
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
