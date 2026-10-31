import { useEffect, useRef, useState } from 'react'
import { browserUrl } from './browser-url'
import { authHeaders, checkResponse } from './workspace-api'

export function useBrowserNavigation(token: string, demo = false) {
  const [notice, setNotice] = useState('')
  const [failed, setFailed] = useState(false)
  const current = useRef<AbortController | null>(null)
  const lastUrl = useRef('')

  useEffect(() => () => { current.current?.abort(); current.current = null }, [])

  async function navigate(value: string) {
    const url = browserUrl(value)
    if (!url || current.current) return
    lastUrl.current = url
    const controller = new AbortController()
    current.current = controller
    setNotice('Sending link to your shop browser…')
    setFailed(false)
    try {
      const response = await fetch(demo ? '/api/chat/navigation' : '/api/operations/navigation', {
        method: 'POST', headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }), signal: controller.signal,
      })
      await checkResponse(response, 'Could not open the link')
      if (!controller.signal.aborted) setNotice('Link sent. Keep your shop browser open and unlocked to view it.')
    } catch (reason) {
      if (!controller.signal.aborted) {
        setFailed(true)
        setNotice(reason instanceof Error ? reason.message : 'Could not open the link. Please try again.')
      }
    } finally { if (current.current === controller) current.current = null }
  }

  return { notice, failed, dismiss: () => setNotice(''), navigate: (url: string) => { void navigate(url) }, retry: () => { void navigate(lastUrl.current) } }
}
