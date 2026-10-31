import { Fragment, useLayoutEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { displayTime } from './browser-url'
import { ArtifactDownload } from './artifact-download'
import { ChatActionsMenu } from './chat-actions-menu'
import { conversationDay } from './conversation-date'
import { RichMessage } from './rich-message'
import { useChatController } from './use-chat-controller'
import { useConversationScroll } from './use-conversation-scroll'

export function ChatClient({ token, onNavigate, onLock, navigation, reports = false, demo = false }: {
  token: string
  reports?: boolean
  demo?: boolean
  onNavigate: (url: string) => void
  onLock: () => void
  navigation: { notice: string; failed: boolean; retry: () => void; dismiss: () => void }
}) {
  const chat = useChatController(token)
  const [draft, setDraft] = useState('')
  const [outputMode, setOutputMode] = useState<'text' | 'report'>('text')
  const composer = useRef<HTMLTextAreaElement>(null)
  const { conversation, content, awayFromLatest, hasNewContent, onScroll, jumpToLatest } = useConversationScroll(chat.messages, chat.loading, chat.error)

  useLayoutEffect(() => {
    const element = composer.current
    if (!element) return
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, 120)}px`
  }, [draft])

  function submit(event: FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || chat.loading || chat.sending || chat.stopped) return
    jumpToLatest()
    setDraft('')
    void chat.send(text, outputMode)
    composer.current?.focus({ preventScroll: true })
  }

  function reload() {
    jumpToLatest()
    chat.reload()
  }

  return <section className="chat-client" aria-label="Agent chat">
    <header className="chat-header">
      <span className="agent-avatar"><img src="/brand/mark-primary.svg" alt="" /></span>
      <div className="agent-identity"><h1>ShopOps</h1><p>{chat.sending ? 'typing…' : chat.loading ? 'loading conversation…' : chat.error ? 'History needs attention' : 'operations assistant'}</p></div>
      <ChatActionsMenu busy={chat.sending || chat.loading} onReload={reload} onLock={onLock} />
    </header>
    <div className="conversation-stage">
      <div className="conversation" ref={conversation} role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions text" aria-busy={chat.loading || chat.sending} tabIndex={0} onScroll={onScroll}>
        <div className="conversation-content" ref={content}>
          {chat.loading && <p className="conversation-notice" role="status">Loading conversation…</p>}
          {!chat.loading && chat.messages.length === 0 && !chat.error && <div className="chat-empty"><h2>Keep your shop in view.</h2><p>Ask about an issue or talk through your next step. Open message links to review details in your shop browser.</p></div>}
          {chat.messages.map((message, index) => {
            const day = conversationDay(message.created_at)
            const previousDay = index ? conversationDay(chat.messages[index - 1].created_at) : null
            return <Fragment key={message.id}>
              {day && day.key !== previousDay?.key && <div className="conversation-day"><time dateTime={day.key}>{day.label}</time></div>}
              <article className={`chat-bubble ${message.role === 'assistant' ? 'assistant-bubble' : 'user-bubble'}`} aria-label={message.role === 'assistant' ? 'Agent message' : 'Your message'}>
                {message.text ? <RichMessage text={message.text} onNavigate={onNavigate} /> : <span className="typing-indicator" aria-label={chat.sending ? 'Agent is thinking' : 'No response received'}>{chat.sending ? 'Thinking…' : 'No response received'}</span>}
                {reports && message.artifacts?.map(artifact => <ArtifactDownload key={artifact.id} artifact={artifact} token={token} />)}
                <time dateTime={message.created_at}>{displayTime(message.created_at)}</time>
              </article>
            </Fragment>
          })}
          {chat.error && <div className="chat-error" role="alert"><strong>Let’s pick up from your history.</strong><p>{chat.error}</p><small>Use Load conversation below to recover without resending your message.</small></div>}
        </div>
      </div>
      {awayFromLatest && <button type="button" className="jump-latest" onClick={() => { jumpToLatest(); conversation.current?.focus({ preventScroll: true }) }}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v16m-6-6 6 6 6-6" /></svg>{hasNewContent ? 'New reply · Jump to latest' : 'Jump to latest'}</button>}
      <span className="sr-only" role="status">{hasNewContent ? 'New response content below.' : ''}</span>
    </div>
    <div className="composer-area">
      {navigation.notice && <aside className={`navigation-notice ${navigation.failed ? 'navigation-failed' : ''}`} aria-label="Link delivery">
        <div><p role={navigation.failed ? 'alert' : 'status'}>{navigation.notice}</p>{navigation.failed && <button className="text-button" type="button" onClick={navigation.retry}>Retry opening link</button>}</div>
        <button type="button" className="icon-button" aria-label="Dismiss link notice" onClick={navigation.dismiss}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg></button>
      </aside>}
      {chat.sending && <div className="stream-status"><span role="status"><span className="response-dot" aria-hidden="true" />Agent is responding…</span><button type="button" className="text-button" onClick={chat.stop}>Stop response</button></div>}
      {chat.stopped && !chat.loading && <div className="recovery-status" role="group" aria-label="Conversation recovery"><span>Load history to continue</span><button type="button" className="text-button" onClick={reload}>Load conversation</button></div>}
      {demo && chat.stopped && <p role="status">Viewing stopped. The agent may still be working; load history to check.</p>}
      {reports && <label className="report-choice">Response format <select value={outputMode} onChange={event => setOutputMode(event.target.value as 'text' | 'report')} disabled={chat.loading || chat.sending || chat.stopped}><option value="text">Text</option><option value="report">Report</option></select></label>}
      <form className="chat-composer" onSubmit={submit}>
        <label htmlFor="chat-message" className="sr-only">Message</label>
        <textarea id="chat-message" ref={composer} rows={1} maxLength={2000} value={draft} onChange={event => setDraft(event.target.value)} placeholder="Message" disabled={chat.loading || chat.stopped} aria-describedby="composer-hint"
          onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); submit(event) } }} />
        <button type="submit" aria-label="Send message" disabled={!draft.trim() || chat.loading || chat.sending || chat.stopped}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 10 18-7-7 18-3-8-8-3Zm8 3L21 3" /></svg></button>
      </form>
      <p className="sr-only" id="composer-hint">Links open in your shop browser. Shift + Enter for a new line.</p>
    </div>
  </section>
}
