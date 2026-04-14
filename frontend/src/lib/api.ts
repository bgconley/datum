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
  version_id?: string | null
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
  entities: SearchResultEntity[]
}

export interface SearchResultEntity {
  canonical_name: string
  entity_type: string
}

export interface SearchEntityFacet {
  canonical_name: string
  entity_type: string
  count: number
}

export interface SearchResponse {
  results: SearchResultItem[]
  entity_facets: SearchEntityFacet[]
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

export interface TemplateDefinition {
  name: string
  title: string
  description: string
  doc_type: string
  default_folder: string
  filename_prefix: string
}

export interface RenderedTemplate {
  content: string
  doc_type: string
  default_folder: string
}

export interface SavedSearchItem {
  id: string
  name: string
  query_text: string
  filters: Record<string, unknown> | null
  project_id: string | null
  created_at: string | null
}

export interface CollectionItem {
  id: string
  name: string
  description: string | null
  member_count: number
  created_at: string | null
}

export interface CollectionMemberItem {
  document_uid: string
  document_title: string
  canonical_path: string
  added_at: string | null
}

export interface AnnotationItem {
  id: string
  version_id: string
  annotation_type: string
  content: string | null
  start_char: number | null
  end_char: number | null
  created_at: string | null
}

export interface UploadResponse {
  filename: string
  attachment_path: string
  content_hash: string
  blob_path: string
  size_bytes: number
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
  entity_facets: SearchEntityFacet[]
  result_count: number
  latency_ms: number | null
  semantic_enabled: boolean
  rerank_applied: boolean
  message?: string
}

export interface Candidate {
  id: string
  candidate_type: 'decision' | 'requirement' | 'open_question'
  title: string
  context: string | null
  severity: 'high' | 'medium' | 'low'
  decision: string | null
  consequences: string | null
  description: string | null
  priority: string | null
  resolution: string | null
  curation_status: string
  extraction_method: string | null
  confidence: number | null
  source_doc_path: string | null
  source_version: number | null
  created_at: string | null
}

export interface CandidateAction {
  id: string
  curation_status: string
  canonical_record_path: string | null
}

export interface IntelligenceEntitySummary {
  entity_type: string
  canonical_name: string
  count: number
}

export interface OpenQuestionSummary {
  id: string
  question: string
  context: string | null
  age_days: number
  is_stale: boolean
  source_doc_path: string | null
  source_version: number | null
  canonical_record_path: string | null
  created_at: string | null
}

export interface ProjectIntelligenceSummary {
  pending_candidate_count: number
  key_entities: IntelligenceEntitySummary[]
  open_questions: OpenQuestionSummary[]
}

export interface InsightSummary {
  id: string
  insight_type: string
  severity: 'info' | 'warning' | 'critical'
  status: string
  title: string
  explanation: string | null
  confidence: number | null
  evidence: Record<string, unknown> | null
  created_at: string | null
  resolved_at: string | null
}

export interface EntitySummary {
  id: string
  entity_type: string
  canonical_name: string
  mention_count: number
}

export interface EntityMentionDetail {
  document_path: string
  document_title: string | null
  chunk_content_snippet: string
  start_char: number
  end_char: number
  confidence: number
  version_number: number | null
}

export interface EntityRelationshipDetail {
  related_entity: string
  relationship_type: string
  direction: 'incoming' | 'outgoing'
  evidence_text: string | null
  evidence_document_path: string | null
  evidence_document_title: string | null
  evidence_heading_path: string | null
  evidence_version_number: number | null
  evidence_chunk_id: string | null
  evidence_start_char: number | null
  evidence_end_char: number | null
}

export interface EntityDetail {
  id: string
  entity_type: string
  canonical_name: string
  mentions: EntityMentionDetail[]
  relationships: EntityRelationshipDetail[]
  mention_count: number
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
  templates: {
    list: () => fetchJSON<TemplateDefinition[]>(`${API_BASE}/templates`),
    get: (name: string) => fetchJSON<TemplateDefinition>(`${API_BASE}/templates/${encodeURIComponent(name)}`),
    render: (name: string, title: string) =>
      fetchJSON<RenderedTemplate>(
        `${API_BASE}/templates/${encodeURIComponent(name)}/render?title=${encodeURIComponent(title)}`,
      ),
  },
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
    delete: (projectSlug: string, docPath: string) =>
      fetchJSON<{ status: string; archived_path: string }>(
        `${API_BASE}/projects/${projectSlug}/docs/${encodeDocumentPath(docPath)}`,
        {
          method: 'DELETE',
        },
      ),
    listGenerated: (projectSlug: string) =>
      fetchJSON<GeneratedFile[]>(`${API_BASE}/projects/${projectSlug}/docs/generated`),
  },
  filesystem: {
    rename: (projectSlug: string, data: { old_path: string; new_path: string }) =>
      fetchJSON<{ old_path: string; new_path: string }>(`${API_BASE}/projects/${projectSlug}/fs/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }),
    mkdir: (projectSlug: string, data: { path: string }) =>
      fetchJSON<{ path: string }>(`${API_BASE}/projects/${projectSlug}/fs/mkdir`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }),
    delete: (projectSlug: string, docPath: string) =>
      fetchJSON<{ status: string; archived_path: string }>(
        `${API_BASE}/projects/${projectSlug}/fs/${encodeDocumentPath(docPath)}`,
        { method: 'DELETE' },
      ),
  },
  upload: {
    file: async (projectSlug: string, file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch(`${API_BASE}/projects/${projectSlug}/upload`, {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        const body = await response.text()
        throw new Error(`${response.status}: ${body}`)
      }
      return response.json() as Promise<UploadResponse>
    },
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
        entity_facets: fallback.entity_facets,
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
  inbox: {
    list: (slug: string) => fetchJSON<Candidate[]>(`${API_BASE}/projects/${slug}/inbox`),
    accept: (
      slug: string,
      type: Candidate['candidate_type'],
      id: string,
      edits?: Record<string, string>,
    ) =>
      fetchJSON<CandidateAction>(`${API_BASE}/projects/${slug}/inbox/${type}/${id}/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(edits ?? {}),
      }),
    reject: (slug: string, type: Candidate['candidate_type'], id: string) =>
      fetchJSON<CandidateAction>(`${API_BASE}/projects/${slug}/inbox/${type}/${id}/reject`, {
        method: 'POST',
      }),
  },
  intelligence: {
    summary: (slug: string) =>
      fetchJSON<ProjectIntelligenceSummary>(`${API_BASE}/projects/${slug}/intelligence/summary`),
  },
  insights: {
    list: (slug: string, status?: string) =>
      fetchJSON<{ insights: InsightSummary[]; total: number }>(
        `${API_BASE}/projects/${slug}/insights${status ? `?status=${encodeURIComponent(status)}` : ''}`,
      ),
    updateStatus: (slug: string, insightId: string, status: string) =>
      fetchJSON<InsightSummary>(`${API_BASE}/projects/${slug}/insights/${insightId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      }),
  },
  entities: {
    list: (slug: string, entityType?: string) =>
      fetchJSON<{ entities: EntitySummary[]; total: number }>(
        `${API_BASE}/projects/${slug}/entities${entityType ? `?entity_type=${encodeURIComponent(entityType)}` : ''}`,
      ),
    get: (slug: string, entityId: string) =>
      fetchJSON<EntityDetail>(`${API_BASE}/projects/${slug}/entities/${entityId}`),
  },
  savedSearches: {
    list: (slug: string) =>
      fetchJSON<SavedSearchItem[]>(`${API_BASE}/projects/${slug}/saved-searches`),
    create: (
      slug: string,
      data: { name: string; query_text: string; filters?: Record<string, unknown> | null },
    ) =>
      fetchJSON<SavedSearchItem>(`${API_BASE}/projects/${slug}/saved-searches`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }),
    delete: (slug: string, id: string) =>
      fetchJSON<{ status: string }>(`${API_BASE}/projects/${slug}/saved-searches/${id}`, {
        method: 'DELETE',
      }),
  },
  collections: {
    list: (slug: string) =>
      fetchJSON<CollectionItem[]>(`${API_BASE}/projects/${slug}/collections`),
    create: (slug: string, data: { name: string; description?: string | null }) =>
      fetchJSON<CollectionItem>(`${API_BASE}/projects/${slug}/collections`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }),
    remove: (slug: string, id: string) =>
      fetchJSON<{ status: string }>(`${API_BASE}/projects/${slug}/collections/${id}`, {
        method: 'DELETE',
      }),
    members: (slug: string, id: string) =>
      fetchJSON<CollectionMemberItem[]>(`${API_BASE}/projects/${slug}/collections/${id}/members`),
    addMember: (slug: string, id: string, data: { document_uid: string }) =>
      fetchJSON<{ status: string }>(`${API_BASE}/projects/${slug}/collections/${id}/members`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }),
    removeMember: (slug: string, id: string, documentUid: string) =>
      fetchJSON<{ status: string }>(
        `${API_BASE}/projects/${slug}/collections/${id}/members/${encodeURIComponent(documentUid)}`,
        { method: 'DELETE' },
      ),
  },
  annotations: {
    list: (versionId: string) =>
      fetchJSON<AnnotationItem[]>(`${API_BASE}/annotations?version_id=${encodeURIComponent(versionId)}`),
    create: (data: {
      version_id: string
      annotation_type: string
      content?: string | null
      start_char?: number | null
      end_char?: number | null
    }) =>
      fetchJSON<AnnotationItem>(`${API_BASE}/annotations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }),
    delete: (annotationId: string) =>
      fetchJSON<{ status: string }>(`${API_BASE}/annotations/${annotationId}`, {
        method: 'DELETE',
      }),
  },
}
