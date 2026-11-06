// Contact is optional: an absent or malformed link must never stop the CRM.
// All addresses still come from build-time environment configuration.
export function buildContactComposeUrl(baseUrl, email) {
  if (typeof baseUrl !== "string" || typeof email !== "string") return null;
  const recipient = email.trim();
  if (!baseUrl.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(recipient)) return null;
  try {
    const url = new URL(baseUrl.trim());
    if (url.protocol !== "https:" || url.username || url.password) return null;
    url.search = new URLSearchParams({ view: "cm", fs: "1", to: recipient }).toString();
    return url.toString();
  } catch {
    return null;
  }
}