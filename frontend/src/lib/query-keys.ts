export const queryKeys = {
  projects: ['projects'] as const,
  project: (slug: string) => ['projects', slug] as const,
  workspace: (slug: string) => ['projects', slug, 'workspace'] as const,
  document: (slug: string, docPath: string) => ['projects', slug, 'docs', docPath] as const,
  versions: (slug: string, docPath: string) =>
    ['projects', slug, 'docs', docPath, 'versions'] as const,
  versionDiff: (slug: string, docPath: string, versionA: number, versionB: number) =>
    ['projects', slug, 'docs', docPath, 'versions', 'diff', versionA, versionB] as const,
  inbox: (slug: string) => ['projects', slug, 'inbox'] as const,
  intelligenceSummary: (slug: string) => ['projects', slug, 'intelligence', 'summary'] as const,
  insights: (slug: string, status: string = 'open') =>
    ['projects', slug, 'insights', status] as const,
  savedSearches: (slug: string) => ['projects', slug, 'saved-searches'] as const,
  collections: (slug: string) => ['projects', slug, 'collections'] as const,
  documentCollections: (slug: string, documentUid: string) =>
    ['projects', slug, 'document-collections', documentUid] as const,
  collectionMembers: (slug: string, collectionId: string) =>
    ['projects', slug, 'collections', collectionId, 'members'] as const,
  annotations: (versionId: string) => ['annotations', versionId] as const,
  templates: ['templates'] as const,
  entities: (slug: string, entityType?: string) =>
    ['projects', slug, 'entities', entityType ?? 'all'] as const,
  entityDetail: (slug: string, entityId: string) =>
    ['projects', slug, 'entities', entityId] as const,
  commandPaletteEntities: (projectSlug: string | null, seed: string) =>
    ['command-palette', 'entities', projectSlug ?? 'all', seed] as const,
}
