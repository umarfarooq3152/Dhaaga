/** Defensive cleanup for descriptions already stored in Redis before the
 * backend began normalizing Shopify HTML at ingestion. */
export function htmlToPlainText(raw: string): string {
  if (!raw) return '';
  const withBreaks = raw.replace(
    /<br\s*\/?>|<\/(?:p|li|div|h[1-6]|tr|ul|ol)\s*>/gi,
    '\n',
  );
  const document = new DOMParser().parseFromString(withBreaks, 'text/html');
  return (document.body.textContent || '')
    .split('\n')
    .map((line) => line.replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .join('\n');
}
