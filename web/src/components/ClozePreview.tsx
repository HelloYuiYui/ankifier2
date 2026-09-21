import type { ReactNode } from 'react'

const CLOZE_RE = /\{\{c(\d+)::(.*?)(?:::(.*?))?\}\}/g

/**
 * Renders a cloze string with the deletions highlighted.
 *
 * This only *displays* the {{cN::…}} the server produced -- it never parses the
 * [[…]] marker syntax. That grammar lives in cloze.py alone, which is the whole
 * reason /api/cloze/preview exists.
 */
export function ClozePreview({ cloze }: { cloze: string }) {
  if (!cloze) return <span className="muted">—</span>

  const parts: ReactNode[] = []
  let last = 0

  for (const m of cloze.matchAll(CLOZE_RE)) {
    const start = m.index
    if (start > last) parts.push(cloze.slice(last, start))
    const [, n, text, hint] = m
    parts.push(
      <span className="cz" key={`${start}-${n}`}>
        [{text}
        {hint ? `: ${hint}` : ''}]
      </span>,
    )
    last = start + m[0].length
  }

  if (last < cloze.length) parts.push(cloze.slice(last))

  return <span className="preview">{parts}</span>
}
