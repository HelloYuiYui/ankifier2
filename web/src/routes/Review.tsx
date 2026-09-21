import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError, api } from '../api/client'
import { ClozePreview } from '../components/ClozePreview'
import type { CardDraft } from '../api/types'
import { keptDrafts, useBatch } from '../store/batch'

/**
 * One review table for all three kinds.
 *
 * There were two near-identical templates for this, because generated and
 * manual cards arrived by different routes. They are the same shape of thing by
 * the time they get here -- add_one() has always treated them identically -- so
 * `kind` only decides which columns are worth showing.
 */
export function Review() {
  const navigate = useNavigate()
  const drafts = useBatch((s) => s.drafts)
  const keep = useBatch((s) => s.keep)
  const errors = useBatch((s) => s.errors)
  const source = useBatch((s) => s.source)
  const toggleKeep = useBatch((s) => s.toggleKeep)
  const setAllKeep = useBatch((s) => s.setAllKeep)
  const updateDraft = useBatch((s) => s.updateDraft)
  const startAdding = useBatch((s) => s.startAdding)
  const setResults = useBatch((s) => s.setResults)

  const [busy, setBusy] = useState<'dry' | 'real' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const kept = keptDrafts({ drafts, keep })
  const showSenses = drafts.some((d) => d.kind === 'generated')

  const add = async (dryRun: boolean) => {
    if (!kept.length) {
      setError('Nothing is ticked.')
      return
    }
    setBusy(dryRun ? 'dry' : 'real')
    setError(null)
    startAdding()
    try {
      const { results } = await api.addCards({ cards: kept, dryRun })
      setResults(results)
      void navigate('/results')
    } catch (e) {
      const message = e instanceof ApiError ? e.message : String(e)
      setError(message)
      useBatch.getState().fail(message)
    } finally {
      setBusy(null)
    }
  }

  if (!drafts.length) {
    return (
      <div className="panel">
        <p className="empty">
          Nothing to review yet. Start from <Link to="/">Generate</Link> or{' '}
          <Link to="/manual">Manual</Link>.
        </p>
      </div>
    )
  }

  const edit =
    (id: string, field: keyof CardDraft) =>
    (e: React.ChangeEvent<HTMLTextAreaElement>) =>
      updateDraft(id, { [field]: e.target.value })

  return (
    <div className="panel">
      <h2>
        Review — {kept.length} of {drafts.length} selected
      </h2>
      <p className="small muted" style={{ marginTop: 0 }}>
        The spoken text, card front and back are editable. Editing the spoken text gives
        the card its own audio file — it never overwrites a card you have already made.
      </p>

      {errors.length > 0 && (
        <div className="banner warn">
          {errors.length} row{errors.length > 1 ? 's' : ''} produced nothing and cannot
          be added:
          {errors.map((e) => (
            <div key={e.sourceId} className="small">
              <strong>{e.text}</strong> — {e.message}
            </div>
          ))}
        </div>
      )}

      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Keep</th>
              <th>Word</th>
              {showSenses && <th>Sense</th>}
              <th style={{ width: '26%' }}>Spoken text</th>
              <th style={{ width: '26%' }}>Card front</th>
              <th style={{ width: '20%' }}>Back</th>
              {showSenses && <th>Level</th>}
            </tr>
          </thead>
          <tbody>
            {drafts.map((d) => (
              <tr key={d.id} className={keep[d.id] ? undefined : 'dropped'}>
                <td>
                  <input
                    type="checkbox"
                    checked={!!keep[d.id]}
                    onChange={() => toggleKeep(d.id)}
                  />
                </td>
                <td>
                  <div>{d.word}</div>
                  {d.kind !== 'generated' && (
                    <span className="badge neutral">
                      {d.kind === 'as_is' ? 'as is' : 'manual'}
                    </span>
                  )}
                </td>
                {showSenses && (
                  <td className="small muted">{d.senseDescription || '—'}</td>
                )}
                <td>
                  <textarea
                    rows={2}
                    value={d.sentence}
                    onChange={edit(d.id, 'sentence')}
                  />
                </td>
                <td>
                  <textarea
                    rows={2}
                    className="mono"
                    value={d.clozeSentence}
                    onChange={edit(d.id, 'clozeSentence')}
                  />
                  <ClozePreview cloze={d.clozeSentence} />
                </td>
                <td>
                  <textarea
                    rows={2}
                    value={d.translation}
                    onChange={edit(d.id, 'translation')}
                  />
                </td>
                {showSenses && (
                  <td className="small muted">{d.level ?? 'not returned'}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {error && (
        <div className="banner error" style={{ marginTop: 14 }}>
          {error}
        </div>
      )}

      <div className="actions">
        <Link to={source === 'manual' ? '/manual' : '/'}>
          <button>Back</button>
        </Link>
        <button onClick={() => setAllKeep(kept.length !== drafts.length)}>
          {kept.length === drafts.length ? 'Untick all' : 'Tick all'}
        </button>
        <span className="spacer" />
        <button onClick={() => add(true)} disabled={busy !== null}>
          {busy === 'dry' && <span className="spinner" />}
          Dry run
        </button>
        <button className="primary" onClick={() => add(false)} disabled={busy !== null}>
          {busy === 'real' && <span className="spinner" />}
          {busy === 'real' ? 'Adding…' : `Add ${kept.length} to Anki`}
        </button>
      </div>

      <p className="hint-line">
        <strong>Dry run</strong> checks decks, filenames and note types without writing
        to Anki or spending ElevenLabs credits.
      </p>
    </div>
  )
}
