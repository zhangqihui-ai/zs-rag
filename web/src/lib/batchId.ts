/** 生成批次 ID；非 HTTPS / 非 localhost 下 crypto.randomUUID 可能不可用，需降级。 */
export function createBatchId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    try {
      return crypto.randomUUID()
    } catch {
      /* secure context 不可用时降级 */
    }
  }
  const rnd = () => Math.random().toString(16).slice(2, 10)
  return `${Date.now().toString(16)}-${rnd()}${rnd()}`
}
