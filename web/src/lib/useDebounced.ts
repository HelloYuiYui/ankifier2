import { useEffect, useState } from 'react'

/**
 * Delays a value until it stops changing.
 *
 * Keyed on the serialized form rather than the reference, so a caller can build
 * a fresh array every render without restarting the timer forever. The value is
 * round-tripped through JSON for the same reason -- it keeps the effect from
 * having to read a ref during render.
 */
export function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value)
  const serialized = JSON.stringify(value)

  useEffect(() => {
    const timer = setTimeout(() => setSettled(JSON.parse(serialized) as T), ms)
    return () => clearTimeout(timer)
  }, [serialized, ms])

  return settled
}
