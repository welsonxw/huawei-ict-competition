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
  return fetch(`${BASE}${path}${qs}`, { credentials: 'include' }).then(handle)
}

export function apiPost(path, data) {
  const isForm = data instanceof FormData
  return fetch(`${BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: isForm ? undefined : { 'Content-Type': 'application/json' },
    body: isForm ? data : JSON.stringify(data ?? {}),
  }).then(handle)
}

function sendJson(method, path, data) {
  return fetch(`${BASE}${path}`, {
    method,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: data === undefined ? undefined : JSON.stringify(data),
  }).then(handle)
}

export function apiPatch(path, data) {
  return sendJson('PATCH', path, data)
}

export function apiDelete(path) {
  return sendJson('DELETE', path)
}
