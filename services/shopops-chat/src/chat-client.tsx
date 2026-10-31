import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { displayTime } from './browser-url'
import { RichMessage } from './rich-message'
import { useChatController } from './use-chat-controller'

export function ChatClient({ token, onNavigate }: { token: string; onNavigate: (url: string) => void }) {
  const chat = useChatController(token)
  const [draft, setDraft] = useState('')
  const conversation = useRef<HTMLDivElement>(null)
  const composer = useRef<HTMLTextAreaElement>(null)
  const followLatest = useRef(true)

  useEffect(() => {
    const element = conversation.current
    if (element && followLatest.current) element.scrollTop = element.scrollHeight
  }, [chat.messages, chat.loading])

  function submit(event: FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || chat.loading || chat.sending || chat.stopped) return
    followLatest.current = true
    setDraft('')
    void chat.send(text)
    composer.current?.focus()
  }

  return <section className="chat-client" aria-label="Agent chat">
    <div className="pane-heading"><div><span className="eyebrow">ON-CALL COMPANION</span><h2>Agent chat</h2></div><span className="pane-index">02</span></div>
    <div className="phone-shell">
      <header className="chat-header"><span className="agent-avatar" aria-hidden="true">✳</span><div><strong>ShopOps Agent</strong><small>{chat.sending ? 'Responding…' : 'Your operations assistant'}</small></div><button type="button" className="icon-button" aria-label="Load conversation" title="Load conversation" disabled={chat.sending || chat.loading} onClick={chat.reload}>↻</button></header>
      <div className="conversation" ref={conversation} role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions text" aria-busy={chat.loading}
        onScroll={() => { const element = conversation.current; if (element) followLatest.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80 }}>
        <p className="conversation-label">WORKSPACE CONVERSATION</p>
        {chat.loading && <p className="conversation-notice" role="status">Loading conversation…</p>}
        {!chat.loading && chat.messages.length === 0 && <div className="chat-empty"><span aria-hidden="true">↗</span><h3>Keep your shop in view.</h3><p>Ask your agent about an issue. Open links here to review the details in your shop browser.</p></div>}
        {chat.messages.map(message => <article key={message.id} className={`chat-bubble ${message.role === 'assistant' ? 'assistant-bubble' : 'user-bubble'}`} aria-label={message.role === 'assistant' ? 'Agent message' : 'Your message'}>
          {message.role === 'assistant' && <strong className="bubble-author">ShopOps</strong>}
          {message.text ? <RichMessage text={message.text} onNavigate={onNavigate} /> : <span className="typing-indicator" aria-label={chat.sending ? 'Agent is thinking' : 'No response received'}>{chat.sending ? 'Thinking…' : 'No response received'}</span>}
          <time dateTime={message.created_at}>{displayTime(message.created_at)}</time>
        </article>)}
      </div>
      {chat.error && <div className="chat-error" role="alert"><p>{chat.error}</p><button type="button" className="text-button" onClick={chat.reload} disabled={chat.sending}>Load conversation</button><small>Reloading will not resend your message.</small></div>}
      {chat.sending && <div className="stream-status"><span role="status">Agent is responding…</span><button type="button" className="text-button" onClick={chat.stop}>Stop response</button></div>}
      <form className="chat-composer" onSubmit={submit}><label htmlFor="chat-message" className="sr-only">Message</label><textarea id="chat-message" ref={composer} rows={2} maxLength={2000} value={draft} onChange={event => setDraft(event.target.value)} placeholder="Ask about your shop…" disabled={chat.loading || chat.stopped}
        onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); submit(event) } }} /><button type="submit" aria-label="Send message" disabled={!draft.trim() || chat.loading || chat.sending || chat.stopped}>↑</button></form>
    </div>
    <p className="pane-caption">Links open in your shop browser <span aria-hidden="true">↖</span></p>
  </section>
}
