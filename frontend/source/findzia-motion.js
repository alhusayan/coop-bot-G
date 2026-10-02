/* Findzia 156.7.25 — motion reconstructed from the supplied 30 fps recording.
 * No router, fetch interception, search delay, or payment lifecycle changes.
 * All content is visible without this enhancement. */
(function () {
  'use strict';
  if (window.FindziaMotion) return;
  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  const active = new Set(), running = new WeakMap(), roots = new WeakSet();
  const dialogs = new WeakSet(), cards = new WeakSet(), waiting = new Set();
  const ease = 'cubic-bezier(.25,0,.4,1)', quick = 'cubic-bezier(.22,1,.36,1)';
  const timings = Object.freeze({ text: 680, line: 85, image: 420, menu: 380, item: 45, close: 160 });
  let trigger = null, viewportObserver;
  const reduced = () => !!media?.matches;
  const visible = el => !!(el?.isConnected && el.getClientRects().length && !el.closest('[hidden]'));
  const inView = el => { const r = el.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight + 24 && r.right > 0 && r.left < innerWidth; };

  function animate(el, frames, options = {}, cleanup) {
    if (!el?.animate || reduced() || !visible(el)) { cleanup?.(); return null; }
    stop(el);
    let animation;
    try { animation = el.animate(frames, { duration: timings.text, easing: ease, fill: 'backwards', ...options }); }
    catch (_) { cleanup?.(); return null; }
    const entry = { el, animation, cleanup };
    active.add(entry); running.set(el, entry);
    const done = () => {
      if (!active.delete(entry)) return;
      if (running.get(el) === entry) running.delete(el);
      // Remove the finished effect so transforms/filters never retain a layer.
      animation.cancel(); cleanup?.();
    };
    animation.finished.then(done, done);
    return animation;
  }
  function stop(el) { const e = running.get(el); if (e) { active.delete(e); running.delete(el); e.animation.cancel(); e.cleanup?.(); } }
  function reveal(el, delay = 0, type = 'text') {
    const image = type === 'image', ui = type === 'ui';
    return animate(el, [
      { opacity: 0, filter: `blur(${image || ui ? 3 : 8}px)`, translate: `0 ${image || ui ? 6 : 8}px` },
      { opacity: 1, filter: 'blur(0px)', translate: '0 0' }
    ], { duration: ui ? 320 : image ? timings.image : timings.text, easing: image || ui ? quick : ease, delay });
  }

  // Reveal rendered lines, keeping whole words (including Arabic joining) intact.
  // Text is restored after playback; no permanent wrappers or fixed line breaks.
  function lines(el, delay = 0) {
    if (!visible(el) || reduced()) return;
    stop(el);
    if (el.children.length || el.textContent.length > 180) { reveal(el, delay); return; }
    const text = el.textContent, parts = text.split(/(\s+)/), words = [];
    if (parts.filter(p => p.trim()).length > 30 || !/\s/.test(text.trim())) { reveal(el, delay); return; }
    const before = el.getBoundingClientRect(), fragment = document.createDocumentFragment();
    for (const part of parts) {
      if (!part.trim()) { fragment.append(document.createTextNode(part)); continue; }
      const word = document.createElement('span'); word.className = 'fz-motion-word'; word.textContent = part;
      words.push(word); fragment.append(word);
    }
    el.replaceChildren(fragment);
    const restore = () => {
      // Translation or a new assistant response may already have replaced this text.
      if (el.textContent === text && words.every(w => w.parentNode === el)) el.replaceChildren(document.createTextNode(text));
    };
    const after = el.getBoundingClientRect();
    if (Math.abs(after.height - before.height) > 1 || Math.abs(after.width - before.width) > 1) {
      restore(); reveal(el, delay); return;
    }
    const tops = [], wordLines = words.map(word => {
      const y = word.getBoundingClientRect().top;
      let index = tops.findIndex(top => Math.abs(top - y) < 3);
      if (index < 0) { index = tops.length; tops.push(y); }
      return index;
    });
    let remaining = words.length;
    const done = () => { if (--remaining === 0) restore(); };
    words.forEach((word, i) => animate(word, [
      { opacity: 0, filter: 'blur(8px)', translate: '0 8px' },
      { opacity: 1, filter: 'blur(0px)', translate: '0 0' }
    ], { delay: delay + Math.min(wordLines[i], 3) * timings.line }, done));
  }

  function cancelWithin(parent) {
    for (const entry of [...active]) if (entry.el === parent || parent.contains(entry.el)) stop(entry.el);
  }
  function queue(el, index = 0, type = 'image') {
    if (!visible(el) || reduced()) return;
    if (inView(el)) { reveal(el, Math.min(index * 35, 105), type); return; }
    if (!viewportObserver) return; // Visible by default if IntersectionObserver is unavailable.
    el.dataset.fzMotionPending = type; waiting.add(el); viewportObserver.observe(el);
  }
  if (window.IntersectionObserver) viewportObserver = new IntersectionObserver(entries => {
    let index = 0;
    for (const entry of entries) if (entry.isIntersecting) {
      const el = entry.target; viewportObserver.unobserve(el); waiting.delete(el);
      const type = el.dataset.fzMotionPending; delete el.dataset.fzMotionPending;
      reveal(el, Math.min(index++ * 35, 105), type);
    }
  }, { rootMargin: '0px 0px 24px', threshold: 0.01 });

  function results(container, before = new Map()) {
    // Called after card admission/painting. Never wait for a reveal before adding a result.
    let index = 0;
    for (const el of container.querySelectorAll('.fz-card-shell')) {
      if (cards.has(el)) continue;
      cards.add(el);
      const key = el.querySelector('[data-image-key]')?.getAttribute('data-image-key');
      if (key && before.has(key)) continue; // Price changes, sorting and view changes stay stable.
      queue(el, index++);
    }
    for (const el of waiting) if (!el.isConnected) { viewportObserver?.unobserve(el); waiting.delete(el); }
  }
  function hero(root) {
    if (root.dataset.homeState !== 'empty' || reduced()) return;
    lines(root.querySelector('.fz-dark-title'));
    reveal(root.querySelector('[data-dark-photo]'), 140, 'image');
    reveal(root.querySelector('.fz-dark-tap'), 200);
    // Keep the search field visible and immediately focusable, like the anchored composer.
  }

  function menuOrigin(dialog) {
    const r = dialog.getBoundingClientRect(), button = trigger?.getBoundingClientRect();
    const right = button ? button.left + button.width / 2 > r.left + r.width / 2 : dialog.dir === 'rtl';
    const top = Math.max(0, Math.min(r.height - 44, (button?.top ?? r.top) - r.top));
    const left = right ? Math.max(0, r.width - 44) : 0;
    const inset = `${top}px ${Math.max(0, r.width - left - 44)}px ${Math.max(0, r.height - top - 44)}px ${left}px round 22px`;
    dialog.style.setProperty('--fz-motion-menu-origin', `inset(${inset})`);
    return `inset(${inset})`;
  }
  function openDialog(dialog) {
    cancelWithin(dialog);
    if (reduced()) return;
    if (dialog.matches('[data-dark-menu]')) {
      const start = menuOrigin(dialog);
      animate(dialog, [{ opacity: .3, clipPath: start }, { opacity: 1, clipPath: 'inset(0px round 16px)' }], { duration: timings.menu, easing: quick });
      const items = [...dialog.querySelectorAll('.fza-nav-link, .fz-dark-menu-action:not([hidden]), .fza-nav-footer')].filter(visible);
      items.forEach((item, i) => reveal(item, 65 + Math.min(i, 5) * timings.item, 'ui'));
    } else {
      animate(dialog, [{ opacity: 0, translate: '0 10px' }, { opacity: 1, translate: '0 0' }], { duration: 300, easing: quick });
    }
  }
  function mountDialog(dialog) {
    if (dialogs.has(dialog) || !dialog.matches('.fz-guide, .fz-account, [data-dark-menu], [data-preferences]')) return;
    dialogs.add(dialog); dialog.dataset.fzMotionDialog = '';
    let signature = '', frame = 0;
    const content = () => {
      frame = 0;
      if (!dialog.open || reduced()) return;
      // Animate the assistant's new question and its answers, never the editable search dock.
      if (dialog.matches('.fz-guide')) {
        const q = dialog.querySelector('.fz-guide-question');
        const choices = [...dialog.querySelectorAll('.fz-guide-choice, .fz-guide-suggestion')].filter(visible);
        const key = (q?.textContent || '') + choices.map(el => el.textContent).join('|');
        if (!key || key === signature) return;
        signature = key;
        lines(q);
        choices.slice(0, 5).forEach((el, i) => reveal(el, 65 + i * 40, 'ui'));
      } else if (dialog.matches('.fz-account')) {
        const q = dialog.querySelector('.fza-header h2');
        const key = q?.textContent || '';
        if (key === signature) return;
        signature = key;
        // Do not touch checkout frames, wallet buttons, form controls or payment body.
        reveal(q);
      }
    };
    const observer = new MutationObserver(records => {
      if (records.some(r => r.type === 'attributes' && r.target === dialog && r.attributeName === 'open')) {
        if (dialog.open) { signature = ''; openDialog(dialog); }
        else { cancelWithin(dialog); return; }
      }
      if (!frame && dialog.open) frame = requestAnimationFrame(content);
    });
    observer.observe(dialog, { attributes: true, attributeFilter: ['open'], childList: true, subtree: true });
    dialog.addEventListener('close', () => { cancelWithin(dialog); signature = ''; });
    if (dialog.open) { openDialog(dialog); content(); }
  }
  function mount(root, entrance = true) {
    if (roots.has(root)) return;
    roots.add(root); root.dataset.motionVersion = '156.7.25';
    const observer = new MutationObserver(records => {
      if (records.some(r => r.type === 'attributes' && r.target === root && r.oldValue !== root.getAttribute(r.attributeName))) { cancelWithin(root.querySelector('[data-dark-home]') || root); hero(root); }
      for (const r of records) for (const el of r.addedNodes) if (el.nodeType === 1) {
        if (el.matches('dialog')) mountDialog(el);
        el.querySelectorAll('dialog').forEach(mountDialog);
      }
    });
    observer.observe(root, { attributes: true, attributeFilter: ['data-home-state', 'data-lang'], attributeOldValue: true, childList: true, subtree: true });
    root.querySelectorAll('dialog').forEach(mountDialog);
    if (entrance) hero(root);
    document.addEventListener('shopify:section:unload', function dispose(event) {
      if (!event.target?.contains(root)) return;
      observer.disconnect(); cancelWithin(root);
      document.removeEventListener('shopify:section:unload', dispose);
    });
  }
  function boot() {
    // A slow asset download must not hide an already-painted homepage again.
    const paint = window.performance?.getEntriesByName?.('first-contentful-paint')[0];
    const entrance = !paint || performance.now() - paint.startTime < 150;
    document.querySelectorAll('.fz-home').forEach(root => mount(root, entrance));
    const legal = document.querySelector('.legal');
    if (legal && entrance) {
      lines(legal.querySelector('h1'));
      [...legal.querySelectorAll('article > p, article > h2, article > h3, article > ul, article > ol')].forEach((el, i) => queue(el, i, 'text'));
    }
  }
  document.addEventListener('pointerdown', e => { trigger = e.target.closest?.('button,a') || null; }, { passive: true, capture: true });
  document.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') trigger = document.activeElement; }, true);
  // Focus is never left in a temporarily faded control after keyboard navigation.
  document.addEventListener('focusin', e => { for (const item of [...active]) if (item.el === e.target || (item.el.contains(e.target) && !item.el.matches('dialog'))) stop(item.el); });
  const reduceChanged = () => {
    if (!reduced()) return;
    for (const entry of [...active]) stop(entry.el);
    for (const el of waiting) { delete el.dataset.fzMotionPending; viewportObserver?.unobserve(el); }
    waiting.clear();
  };
  if (media?.addEventListener) media.addEventListener('change', reduceChanged);
  else media?.addListener?.(reduceChanged);
  window.addEventListener('pagehide', () => { for (const entry of [...active]) stop(entry.el); });
  window.FindziaMotion = Object.freeze({ version: '156.7.25', timings, results, reveal, mount });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
