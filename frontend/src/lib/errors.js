export function errorText(err, t) {
  if (err.status === 401) return t('err_login')
  if (err.status === 403) return t('err_expert')
  if (err.status === 400 && err.message) return `${t('err_invalid')} ${err.message}`
  if (err.status) return t('err_server')
  return t('err_network')
}
