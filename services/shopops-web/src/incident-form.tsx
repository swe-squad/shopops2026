import { useId, useState } from 'react'
import { BrowserIcon } from './browser-icon'

type IncidentFormProps = {
  saving: boolean
  error: string
  onSave: (title: string, detail: string) => Promise<boolean>
}

export function IncidentForm({ saving, error, onSave }: IncidentFormProps) {
  const id = useId()
  const [title, setTitle] = useState('')
  const [detail, setDetail] = useState('')
  const [saved, setSaved] = useState(false)

  return <form className="incident-form" aria-labelledby={`${id}-heading`} onSubmit={async event => {
    event.preventDefault()
    setSaved(false)
    if (await onSave(title, detail)) { setTitle(''); setDetail(''); setSaved(true) }
  }}>
    <h2 id={`${id}-heading`}>Add an incident</h2>
    <div className="field"><label htmlFor={`${id}-title`}>Title</label><input id={`${id}-title`} placeholder="What needs attention?" value={title} onChange={event => { setTitle(event.target.value); setSaved(false) }} maxLength={200} required disabled={saving} /></div>
    <div className="field"><label htmlFor={`${id}-detail`}>Details <span className="muted">(optional)</span></label><textarea id={`${id}-detail`} placeholder="Add context, order references, or what you noticed." rows={4} value={detail} onChange={event => { setDetail(event.target.value); setSaved(false) }} maxLength={2000} disabled={saving} /></div>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {saved && <p className="save-confirmation" role="status"><BrowserIcon name="check" />Incident added.</p>}
    <button type="submit" className="primary-button" disabled={saving || !title.trim()}>{saving ? 'Adding incident…' : 'Add incident'}{!saving && <BrowserIcon name="plus" />}</button>
    <p className="form-note">Saved to your workspace. No shop action is taken.</p>
  </form>
}
