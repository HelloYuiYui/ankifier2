import type { Status } from '../api/types'

const LABEL: Record<Status['state'], string> = {
  ok: 'OK',
  skipped: 'Skipped',
  error: 'Failed',
}

/**
 * The status is an enum with an optional detail, so this switches on the state
 * and shows the detail as a tooltip. The old UI substring-matched free-text
 * error strings to decide which badge to draw.
 */
export function StatusBadge({ status, okLabel }: { status: Status; okLabel?: string }) {
  const label =
    status.state === 'ok'
      ? (okLabel ?? LABEL.ok)
      : (status.detail ?? LABEL[status.state])

  return (
    <span className={`badge ${status.state}`} title={status.detail ?? undefined}>
      {label}
    </span>
  )
}
