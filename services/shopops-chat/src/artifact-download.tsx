import { useEffect, useRef, useState } from 'react'
import { downloadArtifact } from './workspace-api'
import type { Artifact } from './workspace-api'

export function ArtifactDownload({ token, artifact }: { token: string; artifact: Artifact }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const active = useRef<AbortController | null>(null)
  useEffect(() => () => active.current?.abort(), [])
  async function download() {
    if (active.current) return
    const controller = new AbortController()
    active.current = controller
    setBusy(true); setError('')
    try { await downloadArtifact(token, artifact, controller.signal) }
    catch (reason) { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Download unavailable.') }
    finally { if (!controller.signal.aborted) setBusy(false); active.current = null }
  }
  return <div className="report-attachment">
    <button type="button" className="text-button" onClick={() => { void download() }} disabled={busy || artifact.availability !== 'available'}>{busy ? 'Downloading…' : `Download ${artifact.filename}`}</button>
    {artifact.availability !== 'available' && <p role="status">This report is no longer available.</p>}
    {error && <p role="alert">{error} You can retry this download without sending another message.</p>}
  </div>
}
