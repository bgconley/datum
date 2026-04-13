import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'

export function useProjectsQuery() {
  return useQuery({
    queryKey: queryKeys.projects,
    queryFn: api.projects.list,
  })
}

export function useProjectWorkspaceQuery(
  projectSlug: string | null,
  options?: { subscribe?: boolean },
) {
  const queryClient = useQueryClient()
  const subscribe = options?.subscribe ?? false

  const query = useQuery({
    queryKey: projectSlug ? queryKeys.workspace(projectSlug) : ['projects', 'workspace', 'idle'],
    queryFn: () => api.projects.workspace(projectSlug!),
    enabled: Boolean(projectSlug),
  })

  useEffect(() => {
    if (!projectSlug || !subscribe) {
      return
    }

    return api.subscribeProjectWorkspace(projectSlug, (snapshot) => {
      queryClient.setQueryData(queryKeys.workspace(projectSlug), snapshot)
      queryClient.setQueryData(queryKeys.project(projectSlug), snapshot.project)
    })
  }, [projectSlug, queryClient, subscribe])

  return query
}
