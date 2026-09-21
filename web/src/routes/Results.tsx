import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError, api } from '../api/client'
import { StatusBadge } from '../components/StatusBadge'
import { useBatch } from '../store/batch'

/**
 * What happened, per card.
 *
 * The drafts are still in the store alongside the results, which is what makes
 * "retry the failures" a re-POST of a subset rather than a re-run of the batch.
 */
export function Results() {
  const navigate = useNavigate()
  const results = useBatch((s) => s.results)
  const drafts = useBatch((s) => s.drafts)
  const setResults = useBatch((s) => s.setResults)
  const resetAll = useBatch((s) => s.resetAll)

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!results?.length) {
    return (
      <div className="panel">
        <p className="empty">
          No results yet. Start from <Link to="/">Generate</Link> or{' '}
          <Link to="/manual">Manual</Link>.
        </p>
      </div>
    )
  }

  const byId = new Map(drafts.map((d) => [d.id, d]))
  const added = results.filter((r) => r.card.state === 'ok').length
  const failed = results.filter(
    (r) => r.card.state === 'error' || r.audio.state === 'error',
  )
  const wasDryRun = results.every((r) => r.card.detail?.startsWith('dry run'))

  const retry = async () => {
    const cards = failed.map((r) => byId.get(r.id)).filter((d) => d !== undefined)
    if (!cards.length) return

    setBusy(true)
    setError(null)
    try {
      const { results: fresh } = await api.addCards({ cards })
      // Splice the retried results back in, leaving the rest as they were.
      const updated = new Map(fresh.map((r) => [r.id, r]))
      setResults(results.map((r) => updated.get(r.id) ?? r))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel">
      <h2>
        {wasDryRun
          ? `Dry run — ${results.length} card${results.length > 1 ? 's' : ''} checked`
          : `Added ${added} of ${results.length} to Anki`}
      </h2>

      {wasDryRun && (
        <div className="banner warn">
          Nothing was written to Anki and no audio was generated.{' '}
          <Link to="/review">Go back</Link> to add them for real.
        </div>
      )}

      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Card</th>
              <th>Deck</th>
              <th>Audio</th>
              <th>Anki</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => {
              const draft = byId.get(r.id)
              return (
                <tr key={r.id}>
                  <td>
                    <div>{draft?.word ?? r.id}</div>
                    {draft && <div className="small muted">{draft.sentence}</div>}
                  </td>
                  <td className="small muted">{r.deck}</td>
                  <td>
                    <StatusBadge status={r.audio} />
                    {r.audioUrl && (
                      // eslint-disable-next-line jsx-a11y/media-has-caption
                      <audio
                        controls
                        preload="none"
                        src={r.audioUrl}
                        style={{ display: 'block', marginTop: 6, height: 30 }}
                      />
                    )}
                  </td>
                  <td>
                    <StatusBadge status={r.card} okLabel="Added" />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {error && (
        <div className="banner error" style={{ marginTop: 14 }}>
          {error}
        </div>
      )}

      <div className="actions">
        <button
          onClick={() => {
            resetAll()
            void navigate('/')
          }}
        >
          Start over
        </button>
        <Link to="/review">
          <button>Back to review</button>
        </Link>
        <span className="spacer" />
        {failed.length > 0 && !wasDryRun && (
          <button className="primary" onClick={retry} disabled={busy}>
            {busy && <span className="spinner" />}
            Retry {failed.length} failed
          </button>
        )}
      </div>
    </div>
  )
}
