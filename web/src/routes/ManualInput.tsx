import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import { ClozePreview } from '../components/ClozePreview'
import type { CardDraft, ClozeResult, ManualRowInput } from '../api/types'
import { emptyManualRow, useBatch } from '../store/batch'
import { useDebounced } from '../lib/useDebounced'

/**
 * The manual flow, in one screen.
 *
 * It used to be input -> POST /manual/run -> review, but building a manual card
 * is pure string work: nothing needed a round trip except the marker rendering
 * itself, and that is batched and debounced here. So the preview column *is*
 * the review step, and you see the finished card as you type it.
 */
export function ManualInput() {
  const navigate = useNavigate()
  const rows = useBatch((s) => s.manualRows)
  const setRows = useBatch((s) => s.setManualRows)
  const setDrafts = useBatch((s) => s.setDrafts)

  const [previews, setPreviews] = useState<Record<string, ClozeResult>>({})
  const [error, setError] = useState<string | null>(null)

  // One request for the whole table, not one per row.
  const clozeRows = useMemo(
    () => rows.filter((r) => r.cloze && r.front.trim()),
    [rows],
  )
  const debounced = useDebounced(
    useMemo(
      () => clozeRows.map((r) => ({ id: r.id, text: r.front })),
      [clozeRows],
    ),
    150,
  )

  useEffect(() => {
    if (!debounced.length) return
    let cancelled = false
    const textOf = new Map(debounced.map((d) => [d.id, d.text]))

    api
      .clozePreview(debounced)
      .then(({ results }) => {
        if (cancelled) return
        // Cached by TEXT, not by row id. Keying by row would show the previous
        // render against text that has already changed; keyed by text, a stale
        // entry simply isn't found, and retyping something hits the cache.
        setPreviews((prev) => ({
          ...prev,
          ...Object.fromEntries(
            results.flatMap((r) => {
              const text = textOf.get(r.id)
              return text === undefined ? [] : [[text, r] as const]
            }),
          ),
        }))
      })
      .catch(() => {
        /* a failed preview is cosmetic; the add path renders server-side anyway */
      })

    return () => {
      cancelled = true
    }
  }, [debounced])

  const patch = (id: string, change: Partial<ManualRowInput>) =>
    setRows(rows.map((r) => (r.id === id ? { ...r, ...change } : r)))

  const addRow = () => setRows([...rows, emptyManualRow()])

  const removeRow = (id: string) => {
    const kept = rows.filter((r) => r.id !== id)
    setRows(kept.length ? kept : [emptyManualRow()])
  }

  const toReview = () => {
    const filled = rows.filter((r) => r.front.trim())
    if (!filled.length) {
      setError('Add at least one card front.')
      return
    }

    const drafts: CardDraft[] = filled.map((r) => {
      // The server rendered these already; fall back to the literal text for a
      // row whose preview has not landed (or that is not a cloze at all).
      const preview = r.cloze ? previews[r.front] : undefined
      const plain = preview?.plain ?? r.front.trim()
      const cloze = preview?.cloze ?? r.front.trim()

      return {
        id: `${r.id}#1`,
        sourceId: r.id,
        kind: 'manual',
        word: r.front.trim(),
        senseNumber: 1,
        senseDescription: '',
        sentence: plain,
        clozeSentence: cloze,
        translation: r.back.trim(),
        hiddenText: '',
        hint: '',
        level: null,
        // Named after the spoken text, so the filename never carries marker
        // punctuation.
        audioStem: plain,
      }
    })

    setDrafts(drafts)
    navigate('/review')
  }

  return (
    <div className="panel">
      <h2>Cards to write by hand</h2>
      <p className="small muted" style={{ marginTop: 0 }}>
        Nothing here touches the AI. Mark what to hide as <code>[[word]]</code>, or{' '}
        <code>[[word:hint]]</code> to show a hint on the card.
      </p>

      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th style={{ width: '44%' }}>Front</th>
              <th style={{ width: '34%' }}>Back</th>
              <th>Cloze</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const preview = row.cloze ? previews[row.front] : undefined
              return (
                <tr key={row.id}>
                  <td>
                    <textarea
                      rows={1}
                      value={row.front}
                      placeholder="Il faut que tu [[sois:être]] là"
                      onChange={(e) => patch(row.id, { front: e.target.value })}
                    />
                    {row.cloze && row.front.trim() && (
                      <div className="preview">
                        {preview ? (
                          <ClozePreview cloze={preview.cloze} />
                        ) : (
                          <span className="muted">…</span>
                        )}
                      </div>
                    )}
                  </td>
                  <td>
                    <textarea
                      rows={1}
                      value={row.back}
                      placeholder="You have to be there"
                      onChange={(e) => patch(row.id, { back: e.target.value })}
                    />
                  </td>
                  <td>
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={row.cloze}
                        onChange={(e) => patch(row.id, { cloze: e.target.checked })}
                      />
                    </label>
                  </td>
                  <td>
                    <button
                      className="icon"
                      onClick={() => removeRow(row.id)}
                      aria-label="Remove row"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {error && <div className="banner error" style={{ marginTop: 14 }}>{error}</div>}

      <div className="actions">
        <button onClick={addRow}>Add row</button>
        <span className="spacer" />
        <button className="primary" onClick={toReview}>
          Review
        </button>
      </div>
    </div>
  )
}
