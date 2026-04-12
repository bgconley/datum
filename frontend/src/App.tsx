import { useState, useEffect } from 'react'
import { Layout } from './components/Layout'
import { DocumentViewer } from './components/DocumentViewer'

export function App() {
  // Simple hash-based routing for Phase 1
  const [route, setRoute] = useState(window.location.hash.slice(2) || '')

  useEffect(() => {
    const handler = () => setRoute(window.location.hash.slice(2))
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])

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
