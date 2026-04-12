import type { FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { Project } from '@/lib/api'

export interface SearchDraft {
  query: string
  project: string
  versionMode: 'current' | 'all' | 'as_of'
  asOf: string
  limit: number
}

interface SearchBarProps {
  value: SearchDraft
  projects: Project[]
  loading?: boolean
  onChange: (next: SearchDraft) => void
  onSearch: () => void | Promise<void>
  onReset: () => void
}

const selectClassName =
  'h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50'

export function SearchBar({
  value,
  projects,
  loading = false,
  onChange,
  onSearch,
  onReset,
}: SearchBarProps) {
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!value.query.trim()) {
      return
    }
    await onSearch()
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-2xl border border-border/80 bg-card/70 p-4 shadow-sm">
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            value={value.query}
            onChange={(event) => onChange({ ...value, query: event.target.value })}
            placeholder="Search documents, APIs, env vars, and design notes"
            className="flex-1"
            autoFocus
          />
          <div className="flex gap-2">
            <Button type="submit" disabled={loading || !value.query.trim()}>
              {loading ? 'Searching...' : 'Search'}
            </Button>
            <Button type="button" variant="outline" onClick={onReset} disabled={loading}>
              Reset
            </Button>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Project
            </span>
            <select
              value={value.project}
              onChange={(event) => onChange({ ...value, project: event.target.value })}
              className={selectClassName}
            >
              <option value="">All projects</option>
              {projects.map((project) => (
                <option key={project.slug} value={project.slug}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Version Scope
            </span>
            <select
              value={value.versionMode}
              onChange={(event) =>
                onChange({
                  ...value,
                  versionMode: event.target.value as SearchDraft['versionMode'],
                })
              }
              className={selectClassName}
            >
              <option value="current">Current only</option>
              <option value="all">All versions</option>
              <option value="as_of">As of timestamp</option>
            </select>
          </label>

          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              As Of
            </span>
            <Input
              type="datetime-local"
              value={value.asOf}
              onChange={(event) => onChange({ ...value, asOf: event.target.value })}
              disabled={value.versionMode !== 'as_of'}
            />
          </label>

          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Result Limit
            </span>
            <select
              value={value.limit}
              onChange={(event) =>
                onChange({
                  ...value,
                  limit: Number(event.target.value),
                })
              }
              className={selectClassName}
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </label>
        </div>

        <div className="text-xs leading-5 text-muted-foreground">
          Use project scope for focused lookup, switch to all versions for archaeology, or use
          as-of mode to search the state of the cabinet at a prior timestamp.
        </div>
      </div>
    </form>
  )
}
