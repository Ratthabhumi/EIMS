/** PDF uses HTML templates; unlike React text nodes, interpolation needs escaping. */
export function escapeReportData<T>(value: T): T {
  if (typeof value === 'string') return value.replace(/[&<>"']/g, c => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;',
  }[c]!)) as T;
  if (Array.isArray(value)) return value.map(escapeReportData) as T;
  if (value && typeof value === 'object') return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, escapeReportData(item)]),
  ) as T;
  return value;
}
