export type Incident = { id: number; title: string; detail: string; created_at: string }

export function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` }
}

export async function checkResponse(response: Response, action: string) {
  if (response.ok) return
  if (response.status === 401) throw new Error("Workspace token is not valid. Lock the workspace and try again.")
  throw new Error(`${action} (${response.status}). Please try again.`)
}
