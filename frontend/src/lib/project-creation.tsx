import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import {
  CreateProjectDialog,
  type ProjectCreationSource,
} from '@/components/CreateProjectDialog'

interface OpenProjectCreationOptions {
  source?: ProjectCreationSource
  defaultName?: string
}

interface ProjectCreationState {
  open: boolean
  source: ProjectCreationSource
  defaultName: string
}

interface ProjectCreationContextValue {
  openCreateProjectDialog: (options?: OpenProjectCreationOptions) => void
  closeCreateProjectDialog: () => void
}

const DEFAULT_STATE: ProjectCreationState = {
  open: false,
  source: 'unknown',
  defaultName: '',
}

const ProjectCreationContext = createContext<ProjectCreationContextValue | null>(null)

export function ProjectCreationProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ProjectCreationState>(DEFAULT_STATE)

  const openCreateProjectDialog = useCallback((options?: OpenProjectCreationOptions) => {
    setState({
      open: true,
      source: options?.source ?? 'unknown',
      defaultName: options?.defaultName ?? '',
    })
  }, [])

  const closeCreateProjectDialog = useCallback(() => {
    setState((current) => ({ ...current, open: false }))
  }, [])

  const value = useMemo(
    () => ({ openCreateProjectDialog, closeCreateProjectDialog }),
    [closeCreateProjectDialog, openCreateProjectDialog],
  )

  return (
    <ProjectCreationContext.Provider value={value}>
      {children}
      <CreateProjectDialog
        open={state.open}
        onOpenChange={(open) => {
          if (open) {
            return
          }
          closeCreateProjectDialog()
        }}
        source={state.source}
        defaultName={state.defaultName}
      />
    </ProjectCreationContext.Provider>
  )
}

export function useProjectCreation() {
  const value = useContext(ProjectCreationContext)
  if (!value) {
    throw new Error('useProjectCreation must be used within ProjectCreationProvider')
  }
  return value
}
