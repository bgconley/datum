export const queryKeys = {
  projects: ['projects'] as const,
  project: (slug: string) => ['projects', slug] as const,
  workspace: (slug: string) => ['projects', slug, 'workspace'] as const,
  document: (slug: string, docPath: string) => ['projects', slug, 'docs', docPath] as const,
  versions: (slug: string, docPath: string) =>
    ['projects', slug, 'docs', docPath, 'versions'] as const,
  versionDiff: (slug: string, docPath: string, versionA: number, versionB: number) =>
    ['projects', slug, 'docs', docPath, 'versions', 'diff', versionA, versionB] as const,
  dashboardEntities: (slug: string, seed: string) =>
    ['projects', slug, 'dashboard', 'entities', seed] as const,
  commandPaletteEntities: (projectSlug: string | null, seed: string) =>
    ['command-palette', 'entities', projectSlug ?? 'all', seed] as const,
}
