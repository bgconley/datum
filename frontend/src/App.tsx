import { useState, useEffect } from 'react'
import { Layout } from './components/Layout'
import { DocumentViewer } from './components/DocumentViewer'
import { SearchPage } from './components/SearchPage'

export function App() {
  // Simple hash-based routing, preserved until the Phase 4 router migration.
  const [route, setRoute] = useState(window.location.hash.slice(2) || '')

  useEffect(() => {
    const handler = () => setRoute(window.location.hash.slice(2))
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const tagName = target?.tagName ?? ''
      const isEditable =
        target?.isContentEditable ||
        ['INPUT', 'TEXTAREA', 'SELECT'].includes(tagName)

      if (event.key === '/' && !event.metaKey && !event.ctrlKey && !event.altKey && !isEditable) {
        event.preventDefault()
        window.location.hash = '#/search'
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  if (route === 'search') {
    return (
      <Layout>
        <SearchPage />
      </Layout>
    )
  }

  // Parse route: projectSlug/docs/path/to/doc.md
  const parts = route.split('/')
  const projectSlug = parts[0] || null
  const docPath = parts.length > 1 ? parts.slice(1).join('/') : null

  return (
    <Layout>
      {projectSlug && docPath ? (
        <DocumentViewer projectSlug={projectSlug} docPath={docPath} />
      ) : (
        <div className="flex items-center justify-center h-full text-muted-foreground">
          Select a document from the sidebar
        </div>
      )}
    </Layout>
  )
}
