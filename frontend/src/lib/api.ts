const API_BASE = '/api/v1'

export interface Project {
  uid: string
  slug: string
  name: string
  description: string | null
  status: string
  tags: string[]
  created: string | null
}

export interface DocumentMeta {
  title: string
  doc_type: string
  status: string
  tags: string[]
  relative_path: string
  version: number
  content_hash: string
  document_uid: string
  created: string | null
  updated: string | null
}

export interface DocumentContent {
  content: string
  metadata: DocumentMeta
}

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init)
  if (!resp.ok) {
    const body = await resp.text()
    throw new Error(`${resp.status}: ${body}`)
  }
  return resp.json()
}

export const api = {
  projects: {
    list: () => fetchJSON<Project[]>(`${API_BASE}/projects`),
    get: (slug: string) => fetchJSON<Project>(`${API_BASE}/projects/${slug}`),
    create: (data: { name: string; slug: string; description?: string; tags?: string[] }) =>
      fetchJSON<Project>(`${API_BASE}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }),
  },
  documents: {
    list: (projectSlug: string) =>
      fetchJSON<DocumentMeta[]>(`${API_BASE}/projects/${projectSlug}/docs`),
    get: (projectSlug: string, docPath: string) =>
      fetchJSON<DocumentContent>(`${API_BASE}/projects/${projectSlug}/docs/${docPath}`),
    create: (projectSlug: string, data: {
      relative_path: string; title: string; doc_type: string; content: string; tags?: string[]
    }) =>
      fetchJSON<DocumentMeta>(`${API_BASE}/projects/${projectSlug}/docs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }),
    save: (projectSlug: string, docPath: string, data: { content: string; base_hash: string }) =>
      fetchJSON<DocumentMeta>(`${API_BASE}/projects/${projectSlug}/docs/${docPath}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }),
  },
}
