export interface ProjectOnboardingState {
  attachmentsCount: number
  documentsCount: number
  generatedFilePaths: string[]
  pendingCandidateCount: number
  sessionCount: number
}

function countMeaningfulGeneratedFiles(paths: string[]) {
  return paths.filter((path) => {
    if (path === '.piq/manifest.yaml') {
      return false
    }
    if (path.startsWith('.piq/project/versions/')) {
      return false
    }
    return true
  }).length
}

export function isProjectOnboardingState(state: ProjectOnboardingState) {
  return (
    state.documentsCount === 0 &&
    state.attachmentsCount === 0 &&
    countMeaningfulGeneratedFiles(state.generatedFilePaths) === 0 &&
    state.pendingCandidateCount === 0 &&
    state.sessionCount === 0
  )
}
