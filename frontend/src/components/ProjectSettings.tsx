import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'

import { useContextPanel } from '@/lib/context-panel'
import { api } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import { useProjectWorkspaceQuery } from '@/lib/workspace-query'

const CARD = 'rounded-[4px] border border-[#e1e8ed] bg-white px-[14px] py-[12px]'
const LABEL = 'text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]'

function ReadOnlyField({
  label,
  value,
  mono = false,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div className="flex flex-col gap-[6px]">
      <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">{label}</span>
      <div
        className={`rounded-[3px] border border-[#d6e0e8] bg-white px-[12px] py-[8px] text-[12px] text-[#333] ${
          mono ? 'font-mono' : ''
        }`}
      >
        {value}
      </div>
    </div>
  )
}

function WorkflowRow({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-t border-[#e1e8ed] py-[10px] first:border-t-0 first:pt-0 last:pb-0">
      <span className="text-[12px] font-medium text-[#1b2431]">{label}</span>
      <span className="text-[12px] text-[#7b8794]">{value}</span>
    </div>
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

  useEffect(() => {
    if (!project) {
      return () => setContent(null)
    }

    setContent(
      <div className="flex flex-col gap-[12px] p-[16px]">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
          CONTEXT: SETTINGS
        </p>
        <p className="text-[11px] leading-5 text-[#7b8794]">
          Home for project metadata and navigation defaults.
        </p>
        <div className="h-px w-full bg-[#e1e8ed]" />
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
          NOW
        </p>
        <ul className="space-y-1 text-[11px] leading-5 text-[#333]">
          <li>• name, slug, description</li>
          <li>• tags and status display</li>
          <li>• search/switch defaults</li>
        </ul>
        <div className="h-px w-full bg-[#e1e8ed]" />
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
          LATER
        </p>
        <ul className="space-y-1 text-[11px] leading-5 text-[#7b8794]">
          <li>• rename, archive, delete</li>
          <li>• still excluded from first code pass</li>
        </ul>
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
        <div>
          <h1 className="text-[18px] font-semibold text-[#1b2431]">Project Settings</h1>
          <p className="mt-1 max-w-[760px] text-[12px] text-[#7b8794]">
            Metadata and navigation defaults that belong to the project itself, with future management actions kept separate.
          </p>
        </div>

        <div className="grid grid-cols-[minmax(0,1fr)_305px] gap-4">
          <div className="flex flex-col gap-4">
            <section className={CARD}>
              <div className={LABEL}>CURRENT SCOPE</div>
              <div className="mt-1 text-[13px] font-semibold text-[#1b2431]">General</div>
              <div className="mt-4 flex flex-col gap-4">
                <ReadOnlyField label="Project Name" value={project.name} />
                <ReadOnlyField label="Slug" value={project.slug} mono />
                <ReadOnlyField
                  label="Description"
                  value={project.description?.trim() || 'No description provided yet.'}
                />
              </div>
            </section>

            <section className={CARD}>
              <div className={LABEL}>CURRENT SCOPE</div>
              <div className="mt-1 text-[13px] font-semibold text-[#1b2431]">Project Metadata</div>
              <div className="mt-4 flex flex-col gap-4">
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">Status</div>
                  <div className="mt-2">
                    <span className="rounded-full bg-[#5cb85c] px-[8px] py-[2px] text-[10px] font-semibold text-white">
                      {project.status.toUpperCase()}
                    </span>
                  </div>
                </div>
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">Tags</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {project.tags.length > 0 ? (
                      project.tags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full bg-[#f3f6f8] px-[8px] py-[2px] text-[10px] font-medium text-[#1b2431]"
                        >
                          {tag}
                        </span>
                      ))
                    ) : (
                      <span className="text-[11px] text-[#7b8794]">No tags applied</span>
                    )}
                  </div>
                </div>
              </div>
            </section>
          </div>

          <div className="flex flex-col gap-4">
            <section className={CARD}>
              <div className={LABEL}>WORKFLOW</div>
              <div className="mt-1 text-[13px] font-semibold text-[#1b2431]">Navigation Defaults</div>
              <div className="mt-4">
                <WorkflowRow label="Project switch behavior" value="Preserve section" />
                <WorkflowRow label="Search default" value={projectSlug ? 'Current project' : 'All projects'} />
                <WorkflowRow label="Projects Home fallback" value="Fallback to home" />
              </div>
            </section>

            <section className={CARD}>
              <div className={LABEL}>FUTURE STATE</div>
              <div className="mt-1 text-[13px] font-semibold text-[#1b2431]">Future Management Actions</div>
              <div className="mt-4 space-y-4 text-[12px] leading-5">
                <div>
                  <div className="font-semibold text-[#1b2431]">Rename project</div>
                  <div className="mt-1 text-[#7b8794]">
                    Requires backend support beyond create/list/get.
                  </div>
                </div>
                <div>
                  <div className="font-semibold text-[#1b2431]">Archive project</div>
                  <div className="mt-1 text-[#7b8794]">
                    Moves inactive projects out of primary navigation without deleting data.
                  </div>
                </div>
                <div>
                  <div className="font-semibold text-[#1b2431]">Delete project</div>
                  <div className="mt-1 text-[#7b8794]">
                    Intentionally excluded from the first implementation pass.
                  </div>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  )
}
