import { useCallback, useEffect, useRef, useState } from 'react'

/* ------------------------------------------------------------------
   Minimal data-loading hook for the console views.

   Each view needs the same four things: the data, a loading flag, a
   readable error, and a way to try again. `BankPortal` writes that out
   longhand per section, which is fine for a handful of call sites and
   repetitive across a dozen.

   The loader is held in a ref rather than a dependency because callers
   pass an inline arrow function; depending on it directly would refetch
   on every render. Callers declare what actually changes the request
   through `deps` and get a stable `reload` for retries.
------------------------------------------------------------------ */

export interface ApiResource<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => void
}

function describe(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return 'Unable to load data from the Sentinel API.'
}

export function useApiResource<T>(
  loader: () => Promise<T>,
  deps: readonly unknown[] = [],
): ApiResource<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [nonce, setNonce] = useState(0)

  const latest = useRef(loader)
  latest.current = loader

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)

    latest
      .current()
      .then((result) => {
        if (alive) setData(result)
      })
      .catch((cause: unknown) => {
        // Surfaced, never swallowed. A console that renders an empty queue
        // when the API is down is worse than one that says it is down: the
        // analyst reads silence as "nothing is happening".
        if (alive) setError(describe(cause))
      })
      .finally(() => {
        if (alive) setLoading(false)
      })

    return () => {
      alive = false
    }
  }, [...deps, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])

  return { data, error, loading, reload }
}
