export function resolveSelectedProject(pathname: string, searchStr?: string) {
  if (pathname.startsWith('/projects/')) {
    return decodeURIComponent(pathname.split('/')[2] ?? '')
  }

  if (pathname === '/search' && searchStr) {
    const params = new URLSearchParams(searchStr.startsWith('?') ? searchStr.slice(1) : searchStr)
    const project = params.get('project')
    return project ? decodeURIComponent(project) : null
  }

  return null
}
