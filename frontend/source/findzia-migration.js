/* Preserve the existing guest session when switching the same storefront to
 * the public API hostname. This never grants credit; the server verifies it. */
(() => {
  let language = '';
  try {
    language = localStorage.getItem('findzia-lang') || '';
    const oldKey = 'findzia-guest-v1:https://coop-bot-g-production.up.railway.app';
    const newKey = 'findzia-guest-v1:https://api.findzia.com';
    if (!localStorage.getItem(newKey)) {
      const token = localStorage.getItem(oldKey);
      if (token) localStorage.setItem(newKey, token);
    }
    // Keep the original key so a DNS rollback does not discard the session.
  } catch (_) { /* Storage may be unavailable in private/restricted browsing. */ }
  // The old section initializes in English. Re-apply the shopper's saved
  // language through its own existing handler after deferred assets mount.
  document.addEventListener('DOMContentLoaded', () => {
    const select = document.querySelector('[data-profile-language-select]');
    if (select && [...select.options].some(option => option.value === language)) {
      select.value = language;
      select.dispatchEvent(new Event('change', {bubbles:true}));
    }
  }, {once:true});
})();
