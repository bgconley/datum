import { useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { ArrowRightLeft, Database, FileText, Network, Radar } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useContextPanel } from '@/lib/context-panel'
import { api } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'

const ENTITY_TYPE_LABELS: Record<string, string> = {
  technology: 'Technology',
  service: 'Service',
  api: 'API',
  endpoint: 'Endpoint',
  table: 'Table',
  column: 'Column',
  model: 'Model',
  field: 'Field',
  schema: 'Schema',
}

function EntityContextPanel({
  canonicalName,
  entityType,
  mentionCount,
  relationshipCount,
}: {
  canonicalName: string
  entityType: string
  mentionCount: number
  relationshipCount: number
}) {
  return (
    <div className="space-y-5 p-5">
      <div>
        <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
          Entity focus
        </div>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">{canonicalName}</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <Badge variant="secondary">{ENTITY_TYPE_LABELS[entityType] ?? entityType}</Badge>
          <Badge variant="outline">{mentionCount} mentions</Badge>
          <Badge variant="outline">{relationshipCount} relationships</Badge>
        </div>
      </div>

      <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
        <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
          Interpretation
        </div>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          Entity detail is evidence-first. Mentions show where the entity appears across the
          cabinet, and relationships capture derived links that can feed Phase 8 collections and
          future lifecycle automation.
        </p>
      </div>
    </div>
  )
}

export function EntityExplorer({
  projectSlug,
  entityId,
}: {
  projectSlug: string
  entityId?: string
}) {
  const navigate = useNavigate()
  const { setContent } = useContextPanel()

  const entitiesQuery = useQuery({
    queryKey: queryKeys.entities(projectSlug),
    queryFn: () => api.entities.list(projectSlug),
    enabled: Boolean(projectSlug),
  })
  const detailQuery = useQuery({
    queryKey: queryKeys.entityDetail(projectSlug, entityId ?? 'none'),
    queryFn: () => api.entities.get(projectSlug, entityId!),
    enabled: Boolean(projectSlug && entityId),
  })

  const entities = entitiesQuery.data?.entities ?? []
  const selected = detailQuery.data ?? null
  const entityTypes = useMemo(
    () => [...new Set(entities.map((entity) => entity.entity_type))].sort(),
    [entities],
  )

  useEffect(() => {
    if (selected) {
      setContent(
        <EntityContextPanel
          canonicalName={selected.canonical_name}
          entityType={selected.entity_type}
          mentionCount={selected.mention_count}
          relationshipCount={selected.relationships.length}
        />,
      )
      return () => setContent(null)
    }

    setContent(null)
    return () => setContent(null)
  }, [selected, setContent])

  if (entitiesQuery.isLoading) {
    return <div className="p-8 text-muted-foreground">Loading entity graph…</div>
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-8">
      <div className="rounded-[2rem] border border-border/80 bg-card/80 p-8 shadow-sm">
        <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
          Intelligence graph
        </div>
        <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <h1 className="text-3xl font-semibold tracking-tight">Entity explorer</h1>
            <p className="mt-3 text-sm leading-7 text-muted-foreground">
              Inspect the project’s working vocabulary, then drill into evidence-backed mentions
              and relationships. This is the bridge between Phase 5 extraction and Phase 7
              traceability.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{entities.length} entities</Badge>
            {selected && (
              <Badge variant="outline">
                Focus: {selected.canonical_name}
              </Badge>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.88fr_1.12fr]">
        <Card className="bg-card/80">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Network className="size-4" />
              Graph navigator
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {entityTypes.length > 0 && (
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={entityId ? 'outline' : 'secondary'}
                  onClick={() => navigate({ to: '/projects/$slug/entities', params: { slug: projectSlug } })}
                >
                  All
                </Button>
                {entityTypes.map((type) => (
                  <Badge key={type} variant="outline">
                    {ENTITY_TYPE_LABELS[type] ?? type}
                  </Badge>
                ))}
              </div>
            )}

            <ScrollArea className="h-[34rem] pr-3">
              <div className="space-y-2">
                {entities.length === 0 ? (
                  <div className="rounded-2xl border border-border/70 bg-background/70 p-4 text-sm text-muted-foreground">
                    No entities have been extracted yet.
                  </div>
                ) : (
                  entities.map((entity) => {
                    const active = entity.id === entityId
                    return (
                      <Link
                        key={entity.id}
                        to="/projects/$slug/entities/$entityId"
                        params={{ slug: projectSlug, entityId: entity.id }}
                        className={`block rounded-2xl border px-4 py-3 transition-colors ${
                          active
                            ? 'border-foreground/25 bg-foreground text-background'
                            : 'border-border/70 bg-background/70 hover:bg-accent/50'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="truncate font-medium">{entity.canonical_name}</div>
                            <div className="mt-1 text-xs text-current/70">
                              {ENTITY_TYPE_LABELS[entity.entity_type] ?? entity.entity_type}
                            </div>
                          </div>
                          <Badge variant={active ? 'secondary' : 'outline'}>
                            {entity.mention_count}
                          </Badge>
                        </div>
                      </Link>
                    )
                  })
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        <div className="grid gap-6">
          <Card className="bg-card/80">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Radar className="size-4" />
                Selected entity
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!entityId ? (
                <div className="rounded-2xl border border-dashed border-border/70 bg-background/70 p-6 text-sm text-muted-foreground">
                  Pick an entity from the navigator to inspect its evidence trail and graph
                  relationships.
                </div>
              ) : detailQuery.isLoading ? (
                <div className="text-sm text-muted-foreground">Loading entity detail…</div>
              ) : !selected ? (
                <div className="rounded-2xl border border-border/70 bg-background/70 p-6 text-sm text-muted-foreground">
                  Entity not found.
                </div>
              ) : (
                <div className="space-y-5">
                  <div className="flex flex-wrap items-center gap-3">
                    <h2 className="text-2xl font-semibold tracking-tight">
                      {selected.canonical_name}
                    </h2>
                    <Badge variant="secondary">
                      {ENTITY_TYPE_LABELS[selected.entity_type] ?? selected.entity_type}
                    </Badge>
                    <Badge variant="outline">{selected.mention_count} mentions</Badge>
                  </div>

                  <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
                    <div className="space-y-4">
                      <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
                        Evidence ledger
                      </div>
                      {selected.mentions.length === 0 ? (
                        <div className="rounded-2xl border border-border/70 bg-background/70 p-4 text-sm text-muted-foreground">
                          No mentions captured for this entity.
                        </div>
                      ) : (
                        selected.mentions.map((mention, index) => (
                          <div
                            key={`${mention.document_path}-${mention.version_number ?? 'current'}-${index}`}
                            className="rounded-2xl border border-border/70 bg-background/70 p-4"
                          >
                            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                              <Database className="size-3.5" />
                              <span>{mention.document_title ?? mention.document_path}</span>
                              {mention.version_number !== null && (
                                <Badge variant="outline">v{mention.version_number}</Badge>
                              )}
                            </div>
                            <p className="mt-3 text-sm leading-7 text-foreground/90">
                              {mention.chunk_content_snippet}
                            </p>
                            <div className="mt-4 flex items-center justify-between gap-3">
                              <div className="text-xs text-muted-foreground">
                                chars {mention.start_char}-{mention.end_char} · confidence{' '}
                                {mention.confidence.toFixed(2)}
                              </div>
                              <Link
                                to="/projects/$slug/docs/$"
                                params={{ slug: projectSlug, _splat: mention.document_path }}
                                search={{
                                  sourceQuery: selected.canonical_name,
                                  sourceQueryLabel: 'Entity',
                                  sourceSnippet: mention.chunk_content_snippet,
                                  sourceSignals: 'entity-mention',
                                  sourceVersion:
                                    mention.version_number !== null
                                      ? String(mention.version_number)
                                      : undefined,
                                  sourceStart: String(mention.start_char),
                                  sourceEnd: String(mention.end_char),
                                }}
                                className="inline-flex items-center gap-2 text-sm text-foreground/80 transition-colors hover:text-foreground"
                              >
                                Open source
                                <ArrowRightLeft className="size-3.5" />
                              </Link>
                            </div>
                          </div>
                        ))
                      )}
                    </div>

                    <div className="space-y-4">
                      <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
                        Relationship ledger
                      </div>
                      {selected.relationships.length === 0 ? (
                        <div className="rounded-2xl border border-border/70 bg-background/70 p-4 text-sm text-muted-foreground">
                          No graph relationships recorded yet.
                        </div>
                      ) : (
                        selected.relationships.map((relationship, index) => (
                          <div
                            key={`${relationship.direction}-${relationship.related_entity}-${index}`}
                            className="rounded-2xl border border-border/70 bg-background/70 p-4"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant="secondary">{relationship.direction}</Badge>
                              <Badge variant="outline">{relationship.relationship_type}</Badge>
                            </div>
                            <div className="mt-3 flex items-center gap-2 text-sm">
                              <FileText className="size-4 text-muted-foreground" />
                              <span className="font-medium">{relationship.related_entity}</span>
                            </div>
                            {relationship.evidence_text && (
                              <p className="mt-3 text-sm leading-7 text-muted-foreground">
                                {relationship.evidence_text}
                              </p>
                            )}
                            {(relationship.evidence_document_path || relationship.evidence_text) && (
                              <div className="mt-4 flex items-center justify-between gap-3">
                                <div className="text-xs text-muted-foreground">
                                  {relationship.evidence_document_title ??
                                    relationship.evidence_document_path ??
                                    'Relationship evidence'}
                                  {relationship.evidence_version_number !== null &&
                                    relationship.evidence_version_number !== undefined && (
                                      <> · v{relationship.evidence_version_number}</>
                                    )}
                                  {relationship.evidence_start_char !== null &&
                                    relationship.evidence_start_char !== undefined &&
                                    relationship.evidence_end_char !== null &&
                                    relationship.evidence_end_char !== undefined && (
                                      <>
                                        {' '}
                                        · chars {relationship.evidence_start_char}-
                                        {relationship.evidence_end_char}
                                      </>
                                    )}
                                </div>
                                {relationship.evidence_document_path && (
                                  <Link
                                    to="/projects/$slug/docs/$"
                                    params={{
                                      slug: projectSlug,
                                      _splat: relationship.evidence_document_path,
                                    }}
                                    search={{
                                      sourceQuery:
                                        relationship.direction === 'incoming'
                                          ? `${relationship.related_entity} → ${selected.canonical_name}`
                                          : `${selected.canonical_name} → ${relationship.related_entity}`,
                                      sourceQueryLabel: 'Relationship',
                                      sourceSnippet: relationship.evidence_text ?? undefined,
                                      sourceHeading:
                                        relationship.evidence_heading_path ?? undefined,
                                      sourceSignals: [
                                        'relationship-evidence',
                                        relationship.relationship_type,
                                      ].join(','),
                                      sourceVersion:
                                        relationship.evidence_version_number !== null &&
                                        relationship.evidence_version_number !== undefined
                                          ? String(relationship.evidence_version_number)
                                          : undefined,
                                      sourceStart:
                                        relationship.evidence_start_char !== null &&
                                        relationship.evidence_start_char !== undefined
                                          ? String(relationship.evidence_start_char)
                                          : undefined,
                                      sourceEnd:
                                        relationship.evidence_end_char !== null &&
                                        relationship.evidence_end_char !== undefined
                                          ? String(relationship.evidence_end_char)
                                          : undefined,
                                      sourceChunkId:
                                        relationship.evidence_chunk_id ?? undefined,
                                    }}
                                    className="inline-flex items-center gap-2 text-sm text-foreground/80 transition-colors hover:text-foreground"
                                  >
                                    Open source
                                    <ArrowRightLeft className="size-3.5" />
                                  </Link>
                                )}
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
