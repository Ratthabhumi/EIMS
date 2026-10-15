/** Escape untrusted report strings before interpolating into the PDF export DOM.
 * React-rendered results remain unchanged; this is only for generated HTML.
 */
export function escapeReportData<T>(value: T): T {
  if (typeof value === 'string') {
    const entities: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return value.replace(/[&<>"']/g, char => entities[char]) as T;
  }
  if (Array.isArray(value)) return value.map(item => escapeReportData(item)) as T;
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, escapeReportData(item)])) as T;
  }
  return value;
}
