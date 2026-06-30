/** Detect when an API client received SPA HTML instead of JSON. */
export function isLikelyHtmlPayload(raw: unknown): boolean {
  if (typeof raw !== 'string') {
    return false
  }
  const head = raw.trimStart().slice(0, 64).toLowerCase()
  return head.startsWith('<!doctype html') || head.startsWith('<html')
}
