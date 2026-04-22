import type { DocumentMeta } from '@/lib/api'

export const CUSTOM_FOLDER_VALUE = '__custom__'

export const DEFAULT_DOCUMENT_FOLDERS = [
  'docs',
  'docs/config',
  'docs/decisions',
  'docs/notes',
  'docs/plans',
  'docs/reference',
  'docs/requirements',
  'docs/schema',
  'docs/sessions',
]

export function normalizeDocumentFolderPath(value: string): string {
  const normalized = value
    .trim()
    .replace(/\\/g, '/')
    .replace(/^\/+|\/+$/g, '')

  if (!normalized) {
    return 'docs'
  }

  if (normalized === 'docs' || normalized.startsWith('docs/')) {
    return normalized
  }

  return `docs/${normalized}`
}

export function collectProjectDocumentFolders(
  documents: DocumentMeta[],
  preferred: string[] = [],
): string[] {
  const folders = new Set<string>(DEFAULT_DOCUMENT_FOLDERS)

  for (const entry of preferred) {
    folders.add(normalizeDocumentFolderPath(entry))
  }

  for (const document of documents) {
    const parts = document.relative_path.split('/')
    for (let i = 1; i < parts.length; i += 1) {
      folders.add(normalizeDocumentFolderPath(parts.slice(0, i).join('/')))
    }
  }

  return [...folders].sort((left, right) => left.localeCompare(right))
}

export function formatDocumentFolderLabel(path: string): string {
  return `${normalizeDocumentFolderPath(path).replace(/\/$/, '')}/`
}
