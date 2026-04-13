import CodeMirror from '@uiw/react-codemirror'
import { keymap } from '@codemirror/view'
import { EditorView } from '@codemirror/view'
import { markdown } from '@codemirror/lang-markdown'
import { json } from '@codemirror/lang-json'
import { sql } from '@codemirror/lang-sql'
import { oneDark } from '@codemirror/theme-one-dark'
import type { Extension } from '@codemirror/state'

interface CodeMirrorEditorProps {
  value: string
  onChange: (value: string) => void
  onSave?: () => void
  language?: 'markdown' | 'json' | 'sql' | 'yaml' | 'text'
  readOnly?: boolean
  className?: string
}

function languageExtension(language: CodeMirrorEditorProps['language']): Extension {
  switch (language) {
    case 'json':
      return json()
    case 'sql':
      return sql()
    case 'markdown':
      return markdown()
    case 'yaml':
    case 'text':
    default:
      return []
  }
}

export function CodeMirrorEditor({
  value,
  onChange,
  onSave,
  language = 'markdown',
  readOnly = false,
  className,
}: CodeMirrorEditorProps) {
  return (
    <CodeMirror
      value={value}
      height="100%"
      minHeight="28rem"
      theme={oneDark}
      readOnly={readOnly}
      editable={!readOnly}
      className={className}
      basicSetup={{
        foldGutter: true,
        highlightActiveLine: true,
        highlightActiveLineGutter: true,
        lineNumbers: true,
      }}
      extensions={[
        languageExtension(language),
        EditorView.lineWrapping,
        keymap.of([
          {
            key: 'Mod-s',
            run: () => {
              onSave?.()
              return true
            },
          },
        ]),
      ]}
      onChange={onChange}
    />
  )
}
