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
  commandPaletteEntities: (projectSlug: string | null, seed: string) =>
    ['command-palette', 'entities', projectSlug ?? 'all', seed] as const,
}
