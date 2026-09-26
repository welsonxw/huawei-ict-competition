const BASE = import.meta.env.VITE_API_BASE || ''

async function handle(res) {
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(body.error || `Request failed (${res.status})`)
    err.body = body
    err.status = res.status
    throw err
  }
  return body
}

export function apiGet(path, params) {
  const qs = params ? `?${new URLSearchParams(params)}` : ''
  return fetch(`${BASE}${path}${qs}`).then(handle)
}

export function apiPost(path, data) {
  const isForm = data instanceof FormData
  return fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: isForm ? undefined : { 'Content-Type': 'application/json' },
    body: isForm ? data : JSON.stringify(data ?? {}),
  }).then(handle)
}
