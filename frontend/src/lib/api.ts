const API_BASE = '/api/v1'

function encodeDocumentPath(path: string): string {
  return path
    .split('/')
    .map((segment) => encodeURIComponent(segment))
    .join('/')
}

export interface Project {
  uid: string
  slug: string
  name: string
  description: string | null
  status: string
  tags: string[]
  created: string | null
  filesystem_path: string | null
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

export interface SearchResultItem {
  document_title: string
  document_path: string
  document_type: string
  document_status: string
  project_slug: string
  heading_path: string
  snippet: string
  version_number: number
  content_hash: string
  fused_score: number
  matched_terms: string[]
  document_uid: string
  chunk_id: string
  line_start: number
  line_end: number
  match_signals: string[]
}

export interface SearchResponse {
  results: SearchResultItem[]
  query: string
  result_count: number
  latency_ms: number | null
}

export interface SearchRequestParams {
  query: string
  project?: string
  version_scope?: string
  limit?: number
}

export interface DocumentMoveRequest {
  new_relative_path: string
}

export interface GeneratedFile {
  relative_path: string
  absolute_path: string
  size_bytes: number
}

export interface WorkspaceSnapshot {
  project: Project
  documents: DocumentMeta[]
  generated_files: GeneratedFile[]
}

export interface SearchStreamEvent {
  event: 'phase' | 'error'
  phase?: 'lexical' | 'reranked'
  query: string
  results: SearchResultItem[]
  result_count: number
  latency_ms: number | null
  semantic_enabled: boolean
  rerank_applied: boolean
  message?: string
}

export interface VersionInfo {
  version_number: number
  branch: string
  content_hash: string
  version_file: string
  document_uid: string
  created_at: string
  label?: string
  change_source?: string
  restored_from?: number
  created_by?: string
  indexing_status?: string
}

export interface VersionContent {
  version_number: number
  content: string
  content_hash: string
}

export interface VersionDiff {
  version_a: number
  version_b: number
  diff_text: string
  additions: number
  deletions: number
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
    workspace: (slug: string) =>
      fetchJSON<WorkspaceSnapshot>(`${API_BASE}/projects/${slug}/workspace`),
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
      fetchJSON<DocumentContent>(
        `${API_BASE}/projects/${projectSlug}/docs/${encodeDocumentPath(docPath)}`,
      ),
    create: (projectSlug: string, data: {
      relative_path: string; title: string; doc_type: string; content: string; tags?: string[]
    }) =>
      fetchJSON<DocumentMeta>(`${API_BASE}/projects/${projectSlug}/docs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }),
    save: (projectSlug: string, docPath: string, data: { content: string; base_hash: string }) =>
      fetchJSON<DocumentMeta>(
        `${API_BASE}/projects/${projectSlug}/docs/${encodeDocumentPath(docPath)}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        },
      ),
    move: (projectSlug: string, docPath: string, data: DocumentMoveRequest) =>
      fetchJSON<DocumentMeta>(
        `${API_BASE}/projects/${projectSlug}/docs/${encodeDocumentPath(docPath)}/move`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        },
      ),
    createFolder: (projectSlug: string, data: { relative_path: string }) =>
      fetchJSON<{ relative_path: string }>(`${API_BASE}/projects/${projectSlug}/docs/folders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }),
    listGenerated: (projectSlug: string) =>
      fetchJSON<GeneratedFile[]>(`${API_BASE}/projects/${projectSlug}/docs/generated`),
  },
  versions: {
    list: (projectSlug: string, docPath: string) =>
      fetchJSON<VersionInfo[]>(
        `${API_BASE}/projects/${projectSlug}/docs/${encodeDocumentPath(docPath)}/versions`,
      ),
    getContent: (projectSlug: string, docPath: string, version: number) =>
      fetchJSON<VersionContent>(
        `${API_BASE}/projects/${projectSlug}/docs/${encodeDocumentPath(docPath)}/versions/${version}`,
      ),
    diff: (projectSlug: string, docPath: string, versionA: number, versionB: number) =>
      fetchJSON<VersionDiff>(
        `${API_BASE}/projects/${projectSlug}/docs/${encodeDocumentPath(docPath)}/versions/diff/${versionA}/${versionB}`,
      ),
    restore: (projectSlug: string, docPath: string, version: number, data?: { label?: string }) =>
      fetchJSON<DocumentMeta>(
        `${API_BASE}/projects/${projectSlug}/docs/${encodeDocumentPath(docPath)}/versions/${version}/restore`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data ?? {}),
        },
      ),
  },
  subscribeProjectWorkspace: (
    projectSlug: string,
    onMessage: (snapshot: WorkspaceSnapshot) => void,
  ) => {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    let socket: WebSocket | null = null
    let disposed = false

    const timer = window.setTimeout(() => {
      if (disposed) {
        return
      }

      socket = new WebSocket(
        `${protocol}://${window.location.host}/ws/projects/${encodeURIComponent(projectSlug)}/workspace`,
      )
      socket.onmessage = (event) => {
        onMessage(JSON.parse(event.data) as WorkspaceSnapshot)
      }
    }, 0)

    return () => {
      disposed = true
      window.clearTimeout(timer)
      if (socket && socket.readyState < WebSocket.CLOSING) {
        socket.close()
      }
    }
  },
  search: (params: SearchRequestParams) =>
    fetchJSON<SearchResponse>(`${API_BASE}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    }),
  searchStream: async (
    params: SearchRequestParams,
    onEvent: (event: SearchStreamEvent) => void | Promise<void>,
  ) => {
    const resp = await fetch(`${API_BASE}/search/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
    if (!resp.ok) {
      const body = await resp.text()
      throw new Error(`${resp.status}: ${body}`)
    }

    if (!resp.body) {
      const fallback = await api.search(params)
      await onEvent({
        event: 'phase',
        phase: 'reranked',
        query: fallback.query,
        results: fallback.results,
        result_count: fallback.result_count,
        latency_ms: fallback.latency_ms,
        semantic_enabled: false,
        rerank_applied: false,
      })
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })

      let newlineIndex = buffer.indexOf('\n')
      while (newlineIndex >= 0) {
        const line = buffer.slice(0, newlineIndex).trim()
        buffer = buffer.slice(newlineIndex + 1)
        if (line) {
          await onEvent(JSON.parse(line) as SearchStreamEvent)
        }
        newlineIndex = buffer.indexOf('\n')
      }

      if (done) {
        const line = buffer.trim()
        if (line) {
          await onEvent(JSON.parse(line) as SearchStreamEvent)
        }
        break
      }
    }
  },
}
