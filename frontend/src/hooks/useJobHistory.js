import { useState, useEffect } from 'react'

/**
 * Fetches traffic snapshot history for a specific job.
 * Used to populate charts on the Results page.
 */
export default function useJobHistory(jobId) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!jobId) {
      setLoading(false)
      return
    }

    let cancelled = false

    const fetchHistory = async () => {
      setLoading(true)
      setError(null)
      try {
        const resp = await fetch(`/api/jobs/${jobId}/history?limit=500`)
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
        const data = await resp.json()
        if (!cancelled) {
          setHistory(data)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    fetchHistory()

    return () => {
      cancelled = true
    }
  }, [jobId])

  return { history, loading, error }
}
