import { Link } from '@tanstack/react-router'

import { ScrollArea } from '@/components/ui/scroll-area'
import type { DocumentMeta, DocumentEntityMention, VersionInfo } from '@/lib/api'

interface ContextPanelProps {
  projectSlug: string
  document: DocumentMeta
  versions: VersionInfo[]
  headings?: Array<{ id: string; level: number; text: string }>
  entityMentions?: DocumentEntityMention[]
}

const SECTION = 'text-[11px] font-semibold text-[#666]'
const DIVIDER = 'h-px w-full bg-[#e1e8ed]'

export function ContextPanel({
  projectSlug,
  document: doc,
  versions,
  headings = [],
  entityMentions = [],
}: ContextPanelProps) {
  const recentVersions = [...versions].slice(-5).reverse()
  const latestVersion = recentVersions[0]

  // Deduplicate entity mentions
  const seen = new Set<string>()
  const uniqueMentions = entityMentions.filter((m) => {
    const key = `${m.entity_type}:${m.canonical_name}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })

  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-[10px] p-[16px]">
        {/* Header */}
        <p className={SECTION}>CONTEXT: DOCUMENT</p>
        <div className={DIVIDER} />

        {/* Version / Updated / By */}
        <div className="flex items-start justify-between text-[11px]">
          <span className="text-[#666]">Version</span>
          <span className="font-medium text-[#333]">v{String(doc.version).padStart(3, '0')}</span>
        </div>
        <div className="flex items-start justify-between text-[11px]">
          <span className="text-[#666]">Updated</span>
          <span className="font-medium text-[#333]">
            {doc.updated ? new Date(doc.updated).toLocaleDateString() : 'N/A'}
          </span>
        </div>
        <div className="flex items-start justify-between text-[11px]">
          <span className="text-[#666]">By</span>
          <span className="font-medium text-[#333]">
            {latestVersion?.change_source ?? 'web-ui'} ({latestVersion?.change_source === 'agent' ? 'Agent' : 'Human'})
          </span>
        </div>

        <div className={DIVIDER} />

        {/* Table of Contents */}
        {headings.length > 0 && (
          <>
            <p className={SECTION}>TABLE OF CONTENTS</p>
            {headings.map((h) => (
              <a
                key={h.id}
                href={`#${h.id}`}
                className="text-[11px] text-[#22a5f1] hover:underline"
                style={{ paddingLeft: h.level > 1 ? `${(h.level - 1) * 12}px` : undefined }}
              >
                {h.level <= 2 ? `${headings.filter((x) => x.level <= h.level).indexOf(h) + 1}. ` : ''}
                {h.text}
              </a>
            ))}
            <div className={DIVIDER} />
          </>
        )}

        {/* Entity Mentions */}
        {uniqueMentions.length > 0 && (
          <>
            <p className={SECTION}>ENTITY MENTIONS ({uniqueMentions.length})</p>
            {uniqueMentions.map((m) => (
              <div key={`${m.entity_type}:${m.canonical_name}`} className="flex items-center gap-[8px]">
                <span className="text-[9px] font-semibold text-[#666]">
                  {m.entity_type.toUpperCase()}
                </span>
                <Link
                  to="/projects/$slug/entities/$entityId"
                  params={{ slug: projectSlug, entityId: m.entity_id }}
                  className="text-[11px] text-[#22a5f1] hover:underline"
                >
                  {m.canonical_name}
                </Link>
              </div>
            ))}
            <div className={DIVIDER} />
          </>
        )}

        {/* Recent Versions */}
        {recentVersions.length > 0 && (
          <>
            <div className="flex items-center justify-between">
              <p className={SECTION}>RECENT VERSIONS</p>
              <Link
                to="/projects/$slug/docs/$"
                params={{ slug: projectSlug, _splat: `${doc.relative_path}/history` }}
                className="text-[10px] text-[#22a5f1] hover:underline"
              >
                Full history
              </Link>
            </div>
            {recentVersions.map((v) => (
              <div key={v.version_number} className="rounded-[4px] border border-[#e1e8ed] bg-[#f7f9fa] px-[12px] py-[8px]">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-medium text-[#333]">
                    v{String(v.version_number).padStart(3, '0')}
                  </span>
                  <span className="text-[10px] text-[#999]">{v.change_source}</span>
                </div>
                <div className="mt-1 text-[10px] text-[#999]">
                  {new Date(v.created).toLocaleString()}
                </div>
                <div className="mt-1 flex gap-[6px]">
                  <span className="rounded-[3px] bg-[#e1e8ed] px-[6px] py-[2px] text-[9px] font-semibold text-[#333]">
                    {v.change_source}
                  </span>
                  <span className="rounded-[3px] bg-[#e1e8ed] px-[6px] py-[2px] text-[9px] font-semibold text-[#333]">
                    indexed
                  </span>
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </ScrollArea>
  )
}
