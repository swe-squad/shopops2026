export function conversationDay(value: string, today = new Date()) {
  const date = new Date(value.endsWith('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
  if (Number.isNaN(date.getTime())) return null
  const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
  const isToday = date.toDateString() === today.toDateString()
  const label = isToday ? 'Today' : date.toLocaleDateString([], {
    month: 'long', day: 'numeric', year: date.getFullYear() !== today.getFullYear() ? 'numeric' : undefined,
  })
  return { key, label }
}
