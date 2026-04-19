import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'

import { useContextPanel } from '@/lib/context-panel'
import { api } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import { useProjectWorkspaceQuery } from '@/lib/workspace-query'

const CARD = 'rounded-[4px] border border-[#e1e8ed] bg-white px-[20px] py-[16px]'
const LABEL = 'text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]'
const VALUE = 'text-[13px] text-[#1b2431]'
const ROW = 'flex items-start justify-between gap-4 border-t border-[#e1e8ed] py-[10px] first:border-t-0 first:pt-0 last:pb-0'

function MetadataRow({
  label,
  value,
  emphasis = false,
}: {
  label: string
  value: string
  emphasis?: boolean
}) {
  return (
    <div className={ROW}>
      <span className="text-[11px] text-[#666]">{label}</span>
      <span className={emphasis ? 'text-[12px] font-semibold text-[#1b2431]' : 'text-[12px] text-[#333]'}>
        {value}
      </span>
    </div>
  )
}

function FutureAction({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <button
      type="button"
      disabled
      className="flex w-full items-start justify-between gap-3 rounded-[4px] border border-[#e1e8ed] bg-[#f8fafb] px-[14px] py-[12px] text-left opacity-70"
    >
      <div>
        <div className="text-[12px] font-semibold text-[#1b2431]">{title}</div>
        <div className="mt-1 text-[11px] leading-5 text-[#666]">{description}</div>
      </div>
      <span className="rounded-[999px] border border-[#d6e0e8] bg-white px-[8px] py-[3px] text-[9px] font-semibold uppercase tracking-[0.14em] text-[#7b8794]">
        Release B
      </span>
    </button>
  )
}

export function ProjectSettings({ projectSlug }: { projectSlug: string }) {
  const { setContent } = useContextPanel()
  const projectQuery = useQuery({
    queryKey: queryKeys.project(projectSlug),
    queryFn: () => api.projects.get(projectSlug),
    enabled: Boolean(projectSlug),
  })
  const workspaceQuery = useProjectWorkspaceQuery(projectSlug)

  const project = projectQuery.data ?? workspaceQuery.data?.project ?? null
  const workspace = workspaceQuery.data

  useEffect(() => {
    if (!project) {
      return () => setContent(null)
    }

    setContent(
      <div className="flex flex-col gap-[10px] p-[16px]">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
          CONTEXT: SETTINGS
        </p>
        <div className="h-px w-full bg-[#e1e8ed]" />
        <div className="flex items-start justify-between text-[11px]">
          <span className="text-[#666]">Mode</span>
          <span className="rounded-[3px] bg-[#f3f6f8] px-[8px] py-[3px] text-[10px] font-semibold text-[#1b2431]">
            Read-only
          </span>
        </div>
        <div className="flex items-start justify-between text-[11px]">
          <span className="text-[#666]">Project</span>
          <span className="font-medium text-[#333]">{project.name}</span>
        </div>
        <div className="flex items-start justify-between text-[11px]">
          <span className="text-[#666]">Slug</span>
          <span className="font-mono text-[#333]">{project.slug}</span>
        </div>
        <div className="h-px w-full bg-[#e1e8ed]" />
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
          RELEASE A
        </p>
        <p className="text-[11px] leading-5 text-[#666]">
          Metadata is rendered from the project API. Rename, archive, delete, and editable defaults
          stay deferred until backend mutation endpoints exist.
        </p>
      </div>,
    )

    return () => setContent(null)
  }, [project, setContent])

  if (projectQuery.isLoading && !project) {
    return <div className="p-8 text-[#666]">Loading project settings…</div>
  }

  if (projectQuery.isError || !project) {
    return <div className="p-8 text-[#666]">Project settings are unavailable.</div>
  }

  return (
    <div className="min-h-full bg-[#f3f6f8] p-6">
      <div className="mx-auto flex max-w-[1180px] flex-col gap-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className={LABEL}>PROJECT SETTINGS</div>
            <h1 className="mt-1 text-[24px] font-semibold text-[#1b2431]">{project.name}</h1>
            <p className="mt-2 max-w-[720px] text-[13px] leading-6 text-[#666]">
              Release A settings are intentionally read-only. This view exposes the canonical
              project metadata and the actual navigation defaults that govern project switching and
              search behavior.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/projects/$slug"
              params={{ slug: projectSlug }}
              className="rounded-[4px] border border-[#d6e0e8] bg-white px-[14px] py-[8px] text-[12px] font-semibold text-[#1b2431] transition hover:border-[#22a5f1] hover:text-[#22a5f1]"
            >
              Back to Dashboard
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-[minmax(0,1fr)_320px] gap-5">
          <div className="flex flex-col gap-5">
            <section className={CARD}>
              <div className={LABEL}>GENERAL</div>
              <div className="mt-4">
                <MetadataRow label="Project name" value={project.name} emphasis />
                <MetadataRow label="Slug" value={project.slug} />
                <MetadataRow
                  label="Description"
                  value={project.description?.trim() || 'No description provided yet.'}
                />
              </div>
            </section>

            <section className={CARD}>
              <div className={LABEL}>PROJECT METADATA</div>
              <div className="mt-4">
                <MetadataRow label="Status" value={project.status.toUpperCase()} emphasis />
                <MetadataRow
                  label="Tags"
                  value={project.tags.length > 0 ? project.tags.join(', ') : 'No tags applied'}
                />
                <MetadataRow
                  label="Created"
                  value={project.created ? new Date(project.created).toLocaleDateString() : 'Unknown'}
                />
                <MetadataRow
                  label="Filesystem path"
                  value={project.filesystem_path ?? 'Unavailable'}
                />
              </div>
            </section>

            <section className={CARD}>
              <div className={LABEL}>NAVIGATION DEFAULTS</div>
              <div className="mt-4 flex flex-col gap-3">
                <div className="rounded-[4px] border border-[#e1e8ed] bg-[#f8fafb] px-[14px] py-[12px]">
                  <div className="text-[12px] font-semibold text-[#1b2431]">
                    Project switch behavior
                  </div>
                  <div className="mt-1 text-[11px] leading-5 text-[#666]">
                    Preserve the active section when the destination supports it. Document-specific
                    routes fall back to the destination dashboard. Search keeps the query and
                    retrieval mode, and swaps the project only when the search was already
                    project-scoped.
                  </div>
                </div>
                <div className="rounded-[4px] border border-[#e1e8ed] bg-[#f8fafb] px-[14px] py-[12px]">
                  <div className="text-[12px] font-semibold text-[#1b2431]">
                    Search defaults
                  </div>
                  <div className="mt-1 text-[11px] leading-5 text-[#666]">
                    Search launched from a project shell defaults to that project. Search launched
                    from Projects Home or a global command defaults to all projects.
                  </div>
                </div>
                <div className="rounded-[4px] border border-[#e1e8ed] bg-[#f8fafb] px-[14px] py-[12px]">
                  <div className="text-[12px] font-semibold text-[#1b2431]">
                    Projects Home fallback
                  </div>
                  <div className="mt-1 text-[11px] leading-5 text-[#666]">
                    The root route remains the workspace home. Recent project visits and the resume
                    card are client-owned preferences rather than persisted project settings.
                  </div>
                </div>
              </div>
            </section>

            <section className={CARD}>
              <div className={LABEL}>FUTURE MANAGEMENT ACTIONS</div>
              <div className="mt-4 flex flex-col gap-3">
                <FutureAction
                  title="Rename project"
                  description="Requires a backend mutation path and explicit filesystem-slug migration rules."
                />
                <FutureAction
                  title="Archive project"
                  description="Requires lifecycle rules around hidden projects, search visibility, and recovery."
                />
                <FutureAction
                  title="Delete project"
                  description="Requires a destructive-action safety model and explicit data retention policy."
                />
              </div>
            </section>
          </div>

          <div className="flex flex-col gap-5">
            <section className={CARD}>
              <div className={LABEL}>WORKSPACE SUMMARY</div>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="rounded-[4px] border border-[#e1e8ed] bg-[#f8fafb] px-[12px] py-[10px]">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#7b8794]">
                    Documents
                  </div>
                  <div className="mt-2 text-[22px] font-semibold text-[#1b2431]">
                    {workspace?.documents.length ?? 0}
                  </div>
                </div>
                <div className="rounded-[4px] border border-[#e1e8ed] bg-[#f8fafb] px-[12px] py-[10px]">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#7b8794]">
                    Attachments
                  </div>
                  <div className="mt-2 text-[22px] font-semibold text-[#1b2431]">
                    {workspace?.attachments.length ?? 0}
                  </div>
                </div>
                <div className="rounded-[4px] border border-[#e1e8ed] bg-[#f8fafb] px-[12px] py-[10px]">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#7b8794]">
                    Generated
                  </div>
                  <div className="mt-2 text-[22px] font-semibold text-[#1b2431]">
                    {workspace?.generated_files.length ?? 0}
                  </div>
                </div>
                <div className="rounded-[4px] border border-[#e1e8ed] bg-[#f8fafb] px-[12px] py-[10px]">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#7b8794]">
                    Mode
                  </div>
                  <div className="mt-2 text-[14px] font-semibold text-[#1b2431]">Read-only</div>
                </div>
              </div>
            </section>

            <section className={CARD}>
              <div className={LABEL}>IMPLEMENTATION NOTES</div>
              <div className="mt-4 flex flex-col gap-3 text-[11px] leading-5 text-[#666]">
                <p>
                  Project metadata above is server-backed and reflects the canonical project API.
                </p>
                <p>
                  Navigation defaults are descriptive in Release A because their behavior is owned
                  by the frontend shell and route helpers, not persisted project records.
                </p>
                <p>
                  Editable metadata, rename, archive, and delete remain deferred until backend
                  mutation endpoints are defined and safe.
                </p>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  )
}
