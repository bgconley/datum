export interface DocumentTemplate {
  id: string
  label: string
  docType: string
  folder: string
  buildContent: (title: string) => string
}

export const DOCUMENT_TEMPLATES: DocumentTemplate[] = [
  {
    id: 'note',
    label: 'Working note',
    docType: 'plan',
    folder: 'docs/notes',
    buildContent: (title) => `# ${title}\n\n## Context\n\n## Working notes\n\n## Next step\n\n`,
  },
  {
    id: 'adr',
    label: 'Architecture decision',
    docType: 'decision',
    folder: 'docs/adr',
    buildContent: (title) =>
      `# ${title}\n\n## Status\n\nProposed\n\n## Context\n\n## Decision\n\n## Consequences\n\n`,
  },
  {
    id: 'requirements',
    label: 'Requirements doc',
    docType: 'requirements',
    folder: 'docs/requirements',
    buildContent: (title) =>
      `# ${title}\n\n## Goal\n\n## Requirements\n\n- \n\n## Open questions\n\n- \n\n`,
  },
  {
    id: 'plan',
    label: 'Implementation plan',
    docType: 'plan',
    folder: 'docs/plans',
    buildContent: (title) =>
      `# ${title}\n\n## Scope\n\n## Milestones\n\n1. \n\n## Risks\n\n- \n\n`,
  },
  {
    id: 'session',
    label: 'Session note',
    docType: 'session',
    folder: 'docs/sessions',
    buildContent: (title) =>
      `# ${title}\n\n## Objective\n\n## Changes made\n\n## Follow-up\n\n`,
  },
]

export function getTemplate(templateId: string): DocumentTemplate {
  return DOCUMENT_TEMPLATES.find((template) => template.id === templateId) ?? DOCUMENT_TEMPLATES[0]
}
