import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { browserUrl } from './browser-url'

export function RichMessage({ text, onNavigate }: { text: string; onNavigate: (url: string) => void }) {
  return <div className="rich-message"><Markdown skipHtml remarkPlugins={[remarkGfm]}
    urlTransform={url => browserUrl(url) ?? ''}
    components={{
      a: ({ href, children }) => href ? <a href={href} onClick={event => { event.preventDefault(); onNavigate(href) }} title="Open in shop browser">{children}</a> : <span>{children}</span>,
      pre: ({ children }) => <pre tabIndex={0} role="region" aria-label="Message code">{children}</pre>,
      table: ({ children }) => <div className="markdown-table" tabIndex={0} role="region" aria-label="Message table"><table>{children}</table></div>,
      img: ({ alt }) => <span className="image-placeholder">[Image{alt ? `: ${alt}` : ''}]</span>,
    }}>{text}</Markdown></div>
}
