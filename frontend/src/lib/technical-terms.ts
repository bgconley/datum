export interface TechnicalTerm {
  normalizedText: string
  rawText: string
  termType: string
  startChar: number
  endChar: number
  confidence: number
}

interface HeadingItem {
  id: string
  level: number
  text: string
}

const technicalTermPatterns: Array<{ termType: string; pattern: RegExp; confidence: number }> = [
  {
    termType: 'api_route',
    pattern: /(?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(\/[\w./{}\-:]+)/g,
    confidence: 1,
  },
  {
    termType: 'file_path',
    pattern: /(?<!\w)(\.\.?\/[\w./-]+|\/[\w./-]+(?:\.[\w.-]+)?)/g,
    confidence: 0.9,
  },
  {
    termType: 'env_var',
    pattern: /\b([A-Z][A-Z0-9_]{2,})\b/g,
    confidence: 0.8,
  },
  {
    termType: 'version',
    pattern: /\bv?\d+\.\d+(?:\.\d+)?(?:-[\w.]+)?\b/g,
    confidence: 0.9,
  },
  {
    termType: 'sql_identifier',
    pattern: /(?:FROM|TABLE|JOIN|INTO|UPDATE|INDEX\s+ON)\s+([A-Za-z_][\w$]*)/gi,
    confidence: 0.9,
  },
  {
    termType: 'package',
    pattern: /(?:pip\s+install|npm\s+install|yarn\s+add)\s+([\w\[\].-]+(?:\s+[\w\[\].-]+)*)/gi,
    confidence: 0.8,
  },
  {
    termType: 'port',
    pattern: /(?::(\d{2,5})(?!\d))|(?:port\s+(\d{2,5}))/gi,
    confidence: 0.7,
  },
]

const envStopwords = new Set([
  'AND',
  'API',
  'CSS',
  'DELETE',
  'FROM',
  'GET',
  'HEAD',
  'HTML',
  'HTTP',
  'HTTPS',
  'INTO',
  'JOIN',
  'JSON',
  'NOT',
  'OPTIONS',
  'PATCH',
  'POST',
  'PUT',
  'SELECT',
  'SQL',
  'TABLE',
  'THE',
  'URL',
  'WHERE',
  'YAML',
])

export function stripFrontmatter(content: string): string {
  return content.replace(/^---[\s\S]*?---\n*/, '')
}

export function slugifyHeading(value: string): string {
  return value
    .toLowerCase()
    .replace(/[`*_~]/g, '')
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
}

export function extractHeadings(markdown: string): HeadingItem[] {
  const headings: HeadingItem[] = []
  const headingCounts = new Map<string, number>()
  let inFence = false

  for (const line of stripFrontmatter(markdown).split('\n')) {
    if (line.trimStart().startsWith('```')) {
      inFence = !inFence
      continue
    }
    if (inFence) {
      continue
    }

    const match = /^(#{1,6})\s+(.+?)\s*$/.exec(line)
    if (!match) {
      continue
    }
    const level = match[1].length
    const text = match[2].replace(/\s+#*$/, '')
    const baseId = slugifyHeading(text)
    const duplicateCount = headingCounts.get(baseId) ?? 0
    headingCounts.set(baseId, duplicateCount + 1)
    headings.push({
      id: duplicateCount === 0 ? baseId : `${baseId}-${duplicateCount + 1}`,
      level,
      text,
    })
  }

  return headings
}

export function extractTechnicalTerms(text: string): TechnicalTerm[] {
  if (!text) {
    return []
  }

  const matches: TechnicalTerm[] = []
  const seenSpans = new Set<string>()

  for (const { termType, pattern, confidence } of technicalTermPatterns) {
    for (const match of text.matchAll(pattern)) {
      const groups = match.slice(1).filter(Boolean)

      if (termType === 'package' && groups[0]) {
        const packageGroup = groups[0]
        let cursor = text.indexOf(packageGroup, match.index ?? 0)
        for (const pkg of packageGroup.split(/\s+/)) {
          const start = text.indexOf(pkg, cursor)
          if (start < 0) {
            continue
          }
          const end = start + pkg.length
          cursor = end
          const spanKey = `${start}:${end}`
          if (seenSpans.has(spanKey)) {
            continue
          }
          seenSpans.add(spanKey)
          matches.push({
            normalizedText: pkg.toLowerCase().split('[', 1)[0],
            rawText: pkg,
            termType,
            startChar: start,
            endChar: end,
            confidence,
          })
        }
        continue
      }

      const rawText = groups[0] ?? match[0]
      if (!rawText) {
        continue
      }

      const startOffset = match[0].indexOf(rawText)
      const startChar = (match.index ?? 0) + Math.max(startOffset, 0)
      const endChar = startChar + rawText.length
      const spanKey = `${startChar}:${endChar}`

      if (seenSpans.has(spanKey)) {
        continue
      }
      if (termType === 'env_var' && envStopwords.has(rawText)) {
        continue
      }

      seenSpans.add(spanKey)
      matches.push({
        normalizedText:
          termType === 'package' || termType === 'sql_identifier'
            ? rawText.toLowerCase()
            : rawText,
        rawText,
        termType,
        startChar,
        endChar,
        confidence,
      })
    }
  }

  return matches.sort((left, right) => left.startChar - right.startChar || left.endChar - right.endChar)
}

export function uniqueTechnicalTerms(terms: TechnicalTerm[], limit = 24): TechnicalTerm[] {
  const unique = new Map<string, TechnicalTerm>()
  for (const term of terms) {
    const key = `${term.termType}:${term.rawText}`
    if (!unique.has(key)) {
      unique.set(key, term)
    }
  }

  return [...unique.values()]
    .sort((left, right) => right.rawText.length - left.rawText.length || left.rawText.localeCompare(right.rawText))
    .slice(0, limit)
}
