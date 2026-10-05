/* FINDZIA_MOTION_RELEASE=156.7.43 — Findzia 156.7.43 — shared motion for live results, loaded images and navigation.
 * No router, fetch interception, search delay, or payment lifecycle changes.
 * All content is visible without this enhancement. */
(function () {
  'use strict';
  if (window.FindziaMotion) return;
  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  const active = new Set(), running = new WeakMap(), roots = new WeakSet();
  const dialogs = new WeakSet(), popovers = new WeakSet(), details = new WeakSet();
  const cards = new WeakSet(), unreadyCards = new WeakSet(), waiting = new Map(), shown = new WeakMap();
  const ease = 'cubic-bezier(.25,0,.4,1)', quick = 'cubic-bezier(.22,1,.36,1)';
  const timings = Object.freeze({ text: 680, line: 85, image: 280, card: 280, ui: 220, menu: 520, item: 45, close: 160 });
  const dialogSelector = '.fz-guide, .fz-account, .fz-insights, [data-dark-menu], [data-preferences]';
  const popoverSelector = '[data-sort-menu], [data-view-menu]';
  const imageSelector = '.fz-media-stage, .fza-product-image, .fz-saved-thumb';
  const directImageSelector = '.fz-insights-hero img, .fz-guide-context img, .fz-for-you-item img';
  let trigger = null, viewportObserver;
  const reduced = () => !!media?.matches;
  const visible = el => !!(el?.isConnected && el.getClientRects().length && !el.closest('[hidden]') && (!el.closest('dialog') || el.closest('dialog').open));
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
    const image = type === 'image', card = type === 'card', ui = type === 'ui';
    return animate(el, [
      { opacity: 0, filter: `blur(${card || image || ui ? 0 : 8}px)`, translate: `0 ${image ? 0 : ui ? 4 : 8}px` },
      { opacity: 1, filter: 'blur(0px)', translate: '0 0' }
    ], { duration: card ? timings.card : ui ? timings.ui : image ? timings.image : timings.text, easing: ease, delay });
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
    for (const [el] of waiting) if (el === parent || parent.contains(el)) { viewportObserver?.unobserve(el); waiting.delete(el); }
  }
  function queue(el, index = 0, type = 'ui', token = 0) {
    // Do not consume a reveal while a newly inserted card/panel is still hidden.
    if (!visible(el)) return false;
    if (shown.get(el) === token || waiting.get(el)?.token === token) return true;
    if (reduced()) { shown.set(el, token); return true; }
    if (inView(el)) {
      shown.set(el, token); waiting.delete(el); viewportObserver?.unobserve(el);
      reveal(el, Math.min(index * 40, 160), type); return true;
    }
    if (!viewportObserver) { shown.set(el, token); return true; }
    // No CSS opacity:0: content remains readable even if an observer fails.
    waiting.set(el, { type, token }); viewportObserver.observe(el); return true;
  }
  if (window.IntersectionObserver) viewportObserver = new IntersectionObserver(entries => {
    let index = 0;
    for (const entry of entries) if (entry.isIntersecting) {
      const el = entry.target, pending = waiting.get(el);
      viewportObserver.unobserve(el); waiting.delete(el);
      if (!pending || !visible(el)) continue;
      shown.set(el, pending.token);
      reveal(el, Math.min(index++ * 40, 120), pending.type);
    }
  }, { rootMargin: '0px 0px 24px', threshold: 0.01 });

  function results(container, before = new Map()) {
    // Called after card admission/painting. Never wait for a reveal before adding a result.
    let index = 0;
    for (const el of container.querySelectorAll('.fz-card-shell')) {
      if (cards.has(el)) continue;
      const key = el.querySelector('[data-image-key]')?.getAttribute('data-image-key');
      if (key && before.has(key) && !unreadyCards.has(el)) { cards.add(el); continue; }
      if (queue(el, index++, 'card')) { cards.add(el); unreadyCards.delete(el); }
      else unreadyCards.add(el);
    }
    container.querySelectorAll('.fz-market-head').forEach((el, i) => queue(el, i, 'text'));
    container.querySelectorAll(imageSelector).forEach(image);
    for (const [el] of waiting) if (!el.isConnected) { viewportObserver?.unobserve(el); waiting.delete(el); }
  }
  function image(stage) {
    // Dialog content is painted repeatedly during auth/credit refreshes. Its
    // section owns the entrance; a cached image must not flash on each clone.
    if (stage?.closest('dialog')) return;
    const img = stage?.matches('img') ? stage : stage?.querySelector('img');
    if (!img?.complete || !img.naturalWidth) return; // The load event will retry, including cloned/cached images.
    const source = img.currentSrc || img.getAttribute('src');
    if (source) queue(stage, 0, 'image', source);
    // Animate the media wrapper: legacy img rules contain filter/opacity !important.
  }
  function revealNodes(container, selector, token) {
    const nodes = [...container.querySelectorAll(selector)].filter(visible);
    const selected = new Set(nodes);
    let i = 0;
    const occurrences = new Map();
    for (const el of nodes) {
      let parent = el.parentNode, nested = false;
      while (parent && parent !== container) { if (selected.has(parent)) { nested = true; break; } parent = parent.parentNode; }
      // Avoid stacking two content reveals on an already animated group.
      if (!nested) {
        // Identity survives replaceChildren(): busy flags and changing balances
        // update the same semantic slot, rather than replaying its entrance.
        const role = selector.split(',').map(s => s.trim()).find(s => el.matches(s));
        const ordinal = occurrences.get(role) || 0;
        occurrences.set(role, ordinal + 1);
        const key = role + ':' + ordinal;
        if (token.seen?.has(key)) continue;
        if (queue(el, i++, el.matches('.fza-product, .fzb-plan') ? 'card' : 'ui', token)) token.seen?.add(key);
      }
    }
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
    if (dialog.matches('[data-dark-menu]') && dialog.dataset.menuDesign) {
      const r = dialog.getBoundingClientRect();
      const candidate = trigger?.getBoundingClientRect();
      const button = candidate?.width && candidate?.height ? candidate : null;
      const x = button ? button.left + button.width / 2 - r.left - r.width / 2 : r.width * .34;
      const y = button ? button.top + button.height / 2 - r.top - r.height / 2 : -r.height * .42;
      animate(dialog, [
        { opacity: .15, transform: `translate(${x}px, ${y}px) scale(.12)` },
        { opacity: 1, transform: 'translate(0px, 0px) scale(1)' }
      ], { duration: timings.menu, easing: 'cubic-bezier(.22,1,.36,1)' });
      [...dialog.querySelectorAll('.fza-nav-link')].filter(visible).forEach((item, i) => {
        animate(item, [{ opacity: 0, translate: '0 5px' }, { opacity: 1, translate: '0 0' }],
          { duration: 260, delay: 80 + i * timings.item, easing: ease });
      });
      reveal(dialog.querySelector('.fza-nav-footer'), 310, 'ui');
    } else if (dialog.matches('[data-dark-menu]')) {
      const start = menuOrigin(dialog);
      animate(dialog, [{ opacity: .3, clipPath: start }, { opacity: 1, clipPath: 'inset(0px round 16px)' }], { duration: timings.menu, easing: 'cubic-bezier(.22,.65,.35,1)' });
      const items = [...dialog.querySelectorAll('.fza-nav-label, .fza-nav-link, .fz-dark-menu-action:not([hidden]), .fza-nav-footer')].filter(visible);
      items.forEach((item, i) => reveal(item, 55 + Math.min(i, 5) * timings.item, 'ui'));
    } else {
      animate(dialog, [{ opacity: 0, translate: '0 10px' }, { opacity: 1, translate: '0 0' }], { duration: 300, easing: quick });
    }
  }
  function mountDialog(dialog) {
    if (dialogs.has(dialog) || !dialog.matches(dialogSelector)) return;
    dialogs.add(dialog); dialog.dataset.fzMotionDialog = '';
    let signature = '', view = '', frame = 0, token = { seen: new Set() };
    const content = () => {
      frame = 0;
      if (!dialog.open || reduced()) return;
      for (const entry of [...active]) if (!entry.el.isConnected) stop(entry.el);
      // Animate the assistant's new question and its answers, never the editable search dock.
      if (dialog.matches('.fz-guide')) {
        const q = dialog.querySelector('.fz-guide-question');
        const choices = [...dialog.querySelectorAll('.fz-guide-choice, .fz-guide-suggestion')].filter(visible);
        const key = (q?.textContent || '') + choices.map(el => el.textContent).join('|');
        if (key && key !== signature) {
          signature = key; reveal(q, 0, 'ui');
          choices.slice(0, 5).forEach((el, i) => reveal(el, i * 25, 'ui'));
        }
        revealNodes(dialog, '.fz-guide-mode, .fz-guide-intro, .fz-guide-tip, .fz-guide-free-answer, .fz-guide-preferences', token);
      } else if (dialog.matches('.fz-account')) {
        const q = dialog.querySelector('.fza-header h2');
        const key = q?.textContent || '';
        const nextView = dialog.dataset.view || key;
        if (nextView !== view) { view = nextView; token = { seen: new Set() }; }
        if (key !== signature) { signature = key; reveal(q, 0, 'ui'); }
        // Only Findzia-owned content. Never animate the checkout host or provider frames.
        revealNodes(dialog, '.fza-page-intro, .fza-empty, .fza-identity, .fza-membership, .fza-group, .fza-tile, .fza-product, .fza-history-line, .fza-list-tools, .fza-usage-summary, .fza-faq, .fza-policy, .fza-plan-empty, .fza-providers, .fza-login-label, .fzb-plan, .fzb-credit-card', token);
        dialog.querySelectorAll(imageSelector).forEach(image);
      } else if (dialog.matches('[data-preferences]')) {
        revealNodes(dialog, '.fz-preferences-head h2, .fz-preferences-field, .fz-setting-row', token);
      } else if (dialog.matches('.fz-insights')) {
        revealNodes(dialog, '.fz-insights-head h2, .fz-insights-hero, .fz-insights-specs, .fz-insights-summary, .fz-insights-section, .fz-insights-comparison, .fz-insights-details', token);
      }
      dialog.querySelectorAll(directImageSelector).forEach(image);
    };
    const observer = new MutationObserver(records => {
      if (records.some(r => r.type === 'attributes' && r.target === dialog && r.attributeName === 'open')) {
        if (dialog.open) { signature = ''; view = ''; token = { seen: new Set() }; openDialog(dialog); }
        else { cancelWithin(dialog); return; }
      }
      if (!frame && dialog.open) frame = requestAnimationFrame(content);
    });
    observer.observe(dialog, { attributes: true, attributeFilter: ['open', 'hidden', 'data-view'], childList: true, subtree: true });
    dialog.addEventListener('close', () => { cancelWithin(dialog); signature = ''; });
    if (dialog.open) { openDialog(dialog); content(); }
  }
  function mountPopover(panel) {
    if (popovers.has(panel)) return;
    popovers.add(panel);
    let wasOpen = false;
    const update = () => {
      const open = visible(panel);
      if (open && !wasOpen) {
        reveal(panel, 0, 'ui');
        // Focused menu items remain immediately usable; the panel carries the reveal.
      } else if (!open) cancelWithin(panel);
      wasOpen = open;
    };
    const observer = new MutationObserver(update);
    observer.observe(panel, { attributes: true, attributeFilter: ['hidden'] });
    panel.addEventListener('toggle', update);
    update();
  }
  function mountDetails(detail) {
    if (details.has(detail) || !detail.matches('.fza-faq, .fz-setting-row, .fz-guide-free-answer, .fz-guide-preferences, .fz-insights-details')) return;
    details.add(detail);
    detail.addEventListener('toggle', () => {
      if (!detail.open) { cancelWithin(detail); return; }
      [...detail.children].filter(el => !el.matches('summary')).forEach((el, i) => reveal(el, Math.min(i * 40, 120), 'ui'));
    });
  }
  function scan(scope) {
    const each = (selector, fn) => {
      if (scope.matches?.(selector)) fn(scope);
      scope.querySelectorAll(selector).forEach(fn);
    };
    each('dialog', mountDialog);
    each(popoverSelector, mountPopover);
    each('details', mountDetails);
    each(imageSelector, image);
    each(directImageSelector, image);
    if (scope.matches?.('img')) image(scope.closest(imageSelector));
    each('.fz-card-shell', el => {
      if (cards.has(el)) return;
      if (queue(el, 0, 'card')) { cards.add(el); unreadyCards.delete(el); }
      else unreadyCards.add(el);
    });
    each('.fz-market-head, .fz-for-you h2, .fz-for-you-item, .fz-saved-row, .fzb-search-notice', el => queue(el, 0, 'ui'));
  }
  function mount(root, entrance = true) {
    if (roots.has(root)) return;
    roots.add(root); root.dataset.motionVersion = '156.7.27';
    const pending = new Set(); let frame = 0;
    const flush = () => {
      frame = 0;
      for (const entry of [...active]) if (!entry.el.isConnected) stop(entry.el);
      for (const el of pending) if (el.isConnected && ![...pending].some(parent => parent !== el && parent.contains(el))) scan(el);
      pending.clear();
      for (const [el] of waiting) if (!el.isConnected) { viewportObserver?.unobserve(el); waiting.delete(el); }
    };
    const observer = new MutationObserver(records => {
      if (records.some(r => r.type === 'attributes' && r.target === root && ['data-home-state', 'data-lang'].includes(r.attributeName) && r.oldValue !== root.getAttribute(r.attributeName))) { cancelWithin(root.querySelector('[data-dark-home]') || root); hero(root); }
      for (const r of records) {
        if (r.type === 'attributes' && r.target === root && r.attributeName === 'data-home-state') pending.add(root);
        if (r.type === 'attributes' && r.attributeName === 'hidden' && !r.target.hidden) pending.add(r.target);
        for (const el of r.addedNodes || []) if (el.nodeType === 1 && !el.matches('.fz-motion-word')) pending.add(el);
      }
      if (pending.size && !frame) frame = requestAnimationFrame(flush);
    });
    observer.observe(root, { attributes: true, attributeFilter: ['data-home-state', 'data-lang', 'hidden'], attributeOldValue: true, childList: true, subtree: true });
    const loaded = event => {
      if (event.target.matches?.('img')) image(event.target.matches(directImageSelector) ? event.target : event.target.closest(imageSelector));
    };
    root.addEventListener('load', loaded, true);
    scan(root);
    if (entrance) hero(root);
    document.addEventListener('shopify:section:unload', function dispose(event) {
      if (!event.target?.contains(root)) return;
      observer.disconnect(); root.removeEventListener('load', loaded, true); cancelWithin(root);
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
    for (const [el, pending] of waiting) { shown.set(el, pending.token); viewportObserver?.unobserve(el); }
    waiting.clear();
  };
  if (media?.addEventListener) media.addEventListener('change', reduceChanged);
  else media?.addListener?.(reduceChanged);
  window.addEventListener('pagehide', () => { for (const entry of [...active]) stop(entry.el); });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) for (const entry of [...active]) stop(entry.el);
  });
  window.FindziaMotion = Object.freeze({ version: '156.7.43', timings, results, image, reveal, mount });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
