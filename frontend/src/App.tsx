import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { type ErrorInfo, type ReactNode, Component } from 'react'

import { NotificationCenter } from '@/components/NotificationCenter'
import { Button } from '@/components/ui/button'

import { queryClient, router } from '@/router'

interface AppErrorBoundaryProps {
  children: ReactNode
}

interface AppErrorBoundaryState {
  error: Error | null
}

class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = {
    error: null,
  }

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Unhandled application error', error, errorInfo)
  }

  render() {
    if (!this.state.error) {
      return this.props.children
    }

    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-8">
        <div className="max-w-lg rounded border border-destructive/30 bg-white p-8 shadow-sm">
          <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-destructive">
            Application error
          </div>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight">Something went wrong</h1>
          <p className="mt-3 text-sm leading-7 text-muted-foreground">
            A component crashed before the workspace could recover. Reload to restore the last
            cabinet state.
          </p>
          <div className="mt-6 flex gap-3">
            <Button
              type="button"
              onClick={() => {
                window.location.reload()
              }}
            >
              Reload
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                this.setState({ error: null })
              }}
            >
              Try again
            </Button>
          </div>
          <pre className="mt-6 overflow-x-auto rounded border border-border bg-muted p-3 text-xs text-muted-foreground">
            {this.state.error.message}
          </pre>
        </div>
      </div>
    )
  }
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppErrorBoundary>
        <RouterProvider router={router} />
        <NotificationCenter />
      </AppErrorBoundary>
    </QueryClientProvider>
  )
}
