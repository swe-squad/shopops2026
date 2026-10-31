import { useEffect, useRef, useState } from 'react'
import { loadMessages, streamMessage } from './workspace-api'
import type { Message } from './workspace-api'

export function useChatController(token: string) {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [stopped, setStopped] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const activeStream = useRef<AbortController | null>(null)
  const activeLoad = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    activeLoad.current = controller
    void loadMessages(token, controller.signal).then(history => {
      if (!controller.signal.aborted) { setMessages(history); setStopped(false) }
    }).catch(reason => {
      if (!controller.signal.aborted) { setStopped(true); setError(reason instanceof Error ? reason.message : 'Could not load the conversation.') }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [token, refresh])

  useEffect(() => () => { activeStream.current?.abort(); activeStream.current = null; activeLoad.current?.abort(); activeLoad.current = null }, [])

  async function send(text: string, outputMode: 'text' | 'report' = 'text') {
    if (activeStream.current || loading || stopped || !text.trim()) return false
    const controller = new AbortController()
    activeStream.current = controller
    const userId = `local-user-${crypto.randomUUID()}`
    const assistantId = `local-assistant-${crypto.randomUUID()}`
    const createdAt = new Date().toISOString()
    setMessages(items => [...items, { id: userId, role: 'user', text, created_at: createdAt }, { id: assistantId, role: 'assistant', text: '', created_at: createdAt }])
    setSending(true)
    setError('')
    try {
      await streamMessage(token, text, controller.signal, event => {
        if (controller.signal.aborted) return
        if (event.type === 'delta') setMessages(items => items.map(item => item.id === assistantId ? { ...item, text: item.text + event.text } : item))
        if (event.type === 'done') setMessages(items => items.map(item => item.id === assistantId ? event.message : item))
      }, outputMode, crypto.randomUUID())
    } catch (reason) {
      if (activeStream.current === controller) {
        setStopped(true)
        setError(controller.signal.aborted ? 'Response stopped. Load the conversation before sending again.' : reason instanceof Error ? reason.message : 'Could not receive the response.')
      }
    } finally {
      if (activeStream.current === controller) { activeStream.current = null; setSending(false) }
    }
    return true
  }

  function stop() { activeStream.current?.abort() }
  function reload() {
    if (activeStream.current) return
    setLoading(true)
    setError('')
    setRefresh(value => value + 1)
  }
  return { messages, loading, sending, error, stopped, send, stop, reload }
}
