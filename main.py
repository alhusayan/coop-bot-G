<style>
  @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Sora:wght@400;500;600;700;800&family=Alexandria:wght@400;500;600;700;800&display=swap');

  #shopify-section-{{ section.id }} {
    /* ===== FINDZIA V23 · editorial search + live store FIFO ===== */
    --fz-ink: #16211f;
    --fz-mint: #45cfa1;
    --fz-mint-deep: #22a37c;
    --fz-mint-soft: #eafaf4;
    --fz-coral: #ef5a2b;
    --fz-coral-soft: #fdefe9;

    --fz-page: #f6f7f6;
    --fz-tile: #f1f2f0;         /* image tile backdrop */
    --fz-cream: #f7f3e9;        /* badge pill, Fanzia-style */
    --fz-muted: #6b7a76;
    --fz-line: #e6e9e7;

    --fz-r-tile: 22px;
    --fz-r-md: 20px;
    --fz-r-lg: 26px;

    --fz-shadow-lg: 0 24px 56px -20px rgba(22, 33, 31, .20);
    --fz-shadow-sm: 0 6px 16px -8px rgba(22, 33, 31, .12);

    --fz-font: 'Sora', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
    --fz-font-ar: 'Alexandria', 'Segoe UI', Tahoma, sans-serif;
    --fz-serif: 'Instrument Serif', 'Times New Roman', Georgia, serif;
    --fz-ease: cubic-bezier(.22, .9, .24, 1);
    --fz-spring: cubic-bezier(.3, 1.25, .35, 1);
  }

  #shopify-section-{{ section.id }} .fz-home,
  #shopify-section-{{ section.id }} .fz-home * { box-sizing: border-box; }

  #shopify-section-{{ section.id }} .fz-home {
    direction: ltr;
    font-family: var(--fz-font);
    color: var(--fz-ink);
    padding: 14px 0 64px;
    background:
      radial-gradient(760px 340px at 50% -8%, rgba(69,207,161,.12), transparent 62%),
      linear-gradient(180deg, #fafbfa 0%, var(--fz-page) 55%, #f4f6f5 100%);
  }

  #shopify-section-{{ section.id }} .fz-home[data-lang="ar"],
  #shopify-section-{{ section.id }} .fz-home[data-lang="ar"] *,
  #shopify-section-{{ section.id }} .fz-home[data-lang="ur"],
  #shopify-section-{{ section.id }} .fz-home[data-lang="ur"] * { font-family: var(--fz-font-ar) !important; }
  #shopify-section-{{ section.id }} .fz-home:not([data-lang="ar"]),
  #shopify-section-{{ section.id }} .fz-home:not([data-lang="ar"]) * { font-family: var(--fz-font) !important; }
  /* the serif heading keeps its face in both languages where it makes sense */
  #shopify-section-{{ section.id }} .fz-home:not([data-lang="ar"]) .fz-results-title { font-family: var(--fz-serif) !important; }
  #shopify-section-{{ section.id }} .fz-home[data-lang="ar"],
  #shopify-section-{{ section.id }} .fz-home[data-lang="ur"] { direction: rtl; }

  #shopify-section-{{ section.id }} .fz-container {
    width: min(1040px, calc(100% - 24px));
    margin: 0 auto;
  }

  /* ================= TOPBAR ================= */
  #shopify-section-{{ section.id }} .fz-topbar {
    display: flex; align-items: center; justify-content: space-between;
    gap: 16px; padding: 12px 16px; margin-bottom: 16px;
    border: 1px solid rgba(22,33,31,.06);
    border-radius: var(--fz-r-md);
    background: rgba(255,255,255,.86);
    backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
    box-shadow: var(--fz-shadow-sm);
  }
  #shopify-section-{{ section.id }} .fz-logo { display:block; max-width: 148px; width:auto; height:auto; }
  #shopify-section-{{ section.id }} .fz-logo-fallback {
    font-size: 23px; font-weight: 800; letter-spacing: -.03em; color: var(--fz-ink);
  }
  #shopify-section-{{ section.id }} .fz-logo-fallback em { font-style: normal; color: var(--fz-mint-deep); }

  #shopify-section-{{ section.id }} .fz-lang-toggle {
    display: inline-flex; gap: 4px; padding: 4px;
    border-radius: 999px; background: #f1f3f2;
    border: 1px solid rgba(22,33,31,.05);
  }
  #shopify-section-{{ section.id }} .fz-lang-btn {
    border: 0; background: transparent; color: var(--fz-muted);
    border-radius: 999px; padding: 9px 16px;
    font-size: 13.5px; font-weight: 700; line-height: 1;
    cursor: pointer; transition: color .2s ease, background .2s ease;
  }
  #shopify-section-{{ section.id }} .fz-lang-btn.is-active { background: var(--fz-ink); color: #fff; }

  /* ================= SEARCH CARD ================= */
  #shopify-section-{{ section.id }} .fz-search-card {
    position: relative;
    max-width: 860px; margin: 0 auto; padding: 18px;
    border-radius: var(--fz-r-lg);
    border: 1px solid rgba(22,33,31,.06);
    background: rgba(255,255,255,.96);
    box-shadow: 0 24px 60px -24px rgba(22,33,31,.24);
    overflow: hidden;
    animation: fzFade .5s var(--fz-ease) both;
  }

  /* ---- the only animated element ---- */
  #shopify-section-{{ section.id }} .fz-rail {
    position: absolute; top: 0; left: 0; right: 0;
    height: 3px; overflow: hidden;
    background: linear-gradient(90deg, var(--fz-mint) 0%, var(--fz-mint-deep) 55%, var(--fz-coral) 100%);
    opacity: .22; transition: opacity .3s ease;
  }
  #shopify-section-{{ section.id }} .fz-rail::after {
    content: ''; position: absolute; top: 0; bottom: 0; left: 0;
    width: 34%;
    background: linear-gradient(90deg, transparent, #fff 45%, transparent);
    transform: translateX(-120%); opacity: 0;
  }
  #shopify-section-{{ section.id }} .fz-search-card.is-busy .fz-rail { opacity: 1; }
  #shopify-section-{{ section.id }} .fz-search-card.is-busy .fz-rail::after {
    opacity: .95; animation: fzRail 1.15s ease-in-out infinite;
  }

  #shopify-section-{{ section.id }} .fz-search-row {
    display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: center;
  }
  #shopify-section-{{ section.id }} .fz-input-wrap { position: relative; min-width: 0; }
  #shopify-section-{{ section.id }} .fz-input {
    width: 100%; height: 74px;
    border-radius: var(--fz-r-md);
    border: 1.5px solid var(--fz-line);
    background: #fbfcfb; color: var(--fz-ink);
    font-size: 18px; font-weight: 500;
    padding: 0 78px 0 54px; outline: none;
    transition: border-color .2s ease, box-shadow .2s ease, background .2s ease;
  }
  #shopify-section-{{ section.id }} .fz-home:is([data-lang="ar"],[data-lang="ur"]) .fz-input { padding: 0 54px 0 78px; }
  #shopify-section-{{ section.id }} .fz-input:focus {
    border-color: var(--fz-mint-deep); background: #fff;
    box-shadow: 0 0 0 4px rgba(69,207,161,.16);
  }
  #shopify-section-{{ section.id }} .fz-input::placeholder { color: #9ba8a4; font-weight: 400; }

  #shopify-section-{{ section.id }} .fz-input-icon {
    position: absolute; top: 50%; left: 19px;
    width: 20px; height: 20px; transform: translateY(-50%);
    color: var(--fz-mint-deep); pointer-events: none;
  }
  #shopify-section-{{ section.id }} .fz-home:is([data-lang="ar"],[data-lang="ur"]) .fz-input-icon { left: auto; right: 19px; }

  #shopify-section-{{ section.id }} .fz-photo-inline {
    position: absolute; top: 50%; right: 10px; transform: translateY(-50%);
    width: 56px; height: 56px; border-radius: 16px; border: 0;
    background: linear-gradient(140deg, #59dcae 0%, var(--fz-mint) 42%, var(--fz-mint-deep) 100%);
    color: #06322a;
    display: inline-flex; align-items: center; justify-content: center;
    cursor: pointer;
    box-shadow: 0 10px 24px -8px rgba(34,163,124,.55);
    transition: transform .2s var(--fz-spring);
  }
  #shopify-section-{{ section.id }} .fz-photo-inline svg { width: 26px; height: 26px; }
  #shopify-section-{{ section.id }} .fz-home:is([data-lang="ar"],[data-lang="ur"]) .fz-photo-inline { right: auto; left: 10px; }
  #shopify-section-{{ section.id }} .fz-photo-inline:hover { transform: translateY(-50%) scale(1.06); }
  #shopify-section-{{ section.id }} .fz-photo-inline:active { transform: translateY(-50%) scale(.96); }
  #shopify-section-{{ section.id }} .fz-photo-inline::after {
    content: ''; position: absolute;
    top: -3px; inset-inline-end: -3px;
    width: 10px; height: 10px; border-radius: 3px;
    background: var(--fz-coral); border: 2px solid #fff;
  }

  #shopify-section-{{ section.id }} .fz-btn {
    height: 74px; display: inline-flex; align-items: center; justify-content: center;
    border: 0; border-radius: var(--fz-r-md); padding: 0 34px;
    font-size: 18px; font-weight: 700; line-height: 1; cursor: pointer;
    transition: transform .18s var(--fz-spring), opacity .2s ease;
    white-space: nowrap;
  }
  #shopify-section-{{ section.id }} .fz-btn-primary {
    background: linear-gradient(140deg, var(--fz-ink) 0%, #253531 100%);
    color: #fff; box-shadow: 0 14px 30px -12px rgba(22,33,31,.6);
    min-width: 158px;
  }
  #shopify-section-{{ section.id }} .fz-btn-primary:hover { transform: translateY(-2px); }
  #shopify-section-{{ section.id }} .fz-btn-primary:active { transform: translateY(0) scale(.985); }
  #shopify-section-{{ section.id }} .fz-btn-primary:disabled { opacity: .5; pointer-events: none; }

  #shopify-section-{{ section.id }} .fz-status {
    display: none; margin-top: 12px;
    font-size: 14px; font-weight: 600; color: var(--fz-muted); text-align: center;
  }
  #shopify-section-{{ section.id }} .fz-status.is-visible { display: block; }

  #shopify-section-{{ section.id }} .fz-wa-row { display: flex; justify-content: center; margin-top: 14px; }
  #shopify-section-{{ section.id }} .fz-wa-btn {
    display: inline-flex; align-items: center; gap: 9px;
    padding: 10px 18px 10px 13px; border-radius: 999px;
    text-decoration: none; color: var(--fz-ink);
    background: #f4f6f5; border: 1px solid rgba(22,33,31,.07);
    font-size: 14px; font-weight: 700;
    transition: background .2s ease, transform .18s ease, border-color .2s ease;
  }
  #shopify-section-{{ section.id }} .fz-home:is([data-lang="ar"],[data-lang="ur"]) .fz-wa-btn { padding: 10px 13px 10px 18px; }
  #shopify-section-{{ section.id }} .fz-wa-btn:hover {
    background: #eef2f0; transform: translateY(-1px); border-color: rgba(37,211,102,.4);
  }
  #shopify-section-{{ section.id }} .fz-wa-icon { width: 22px; height: 22px; flex: 0 0 auto; }

  /* ================= RESULTS — clean editorial product tiles ================= */
  #shopify-section-{{ section.id }} .fz-results-shell {
    display: none;
    margin-top: 34px;
    padding: 0;
    background: transparent;
    border: 0;
    box-shadow: none;
  }
  #shopify-section-{{ section.id }} .fz-results-shell.is-visible { display: block; }

  #shopify-section-{{ section.id }} .fz-results-head {
    display: flex; align-items: baseline; justify-content: space-between;
    gap: 14px; flex-wrap: wrap; margin-bottom: 20px;
  }
  #shopify-section-{{ section.id }} .fz-results-title {
    margin: 0;
    font-family: var(--fz-serif);
    font-size: clamp(30px, 5vw, 40px);
    font-weight: 400;
    letter-spacing: -.01em;
    line-height: 1.1;
    color: var(--fz-ink);
  }
  #shopify-section-{{ section.id }} .fz-home[data-lang="ar"] .fz-results-title {
    font-size: clamp(24px, 4.4vw, 32px); font-weight: 700; line-height: 1.35;
  }
  #shopify-section-{{ section.id }} .fz-results-title span {
    font-size: .42em;
    font-family: var(--fz-font) !important;
    font-weight: 600;
    color: var(--fz-muted);
    letter-spacing: 0;
    margin-inline-start: 10px;
    vertical-align: middle;
  }

  /* controls — quiet editorial text links */
  #shopify-section-{{ section.id }} .fz-controls {
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  }
  #shopify-section-{{ section.id }} .fz-seg { display: inline-flex; align-items: center; gap: 12px; }
  #shopify-section-{{ section.id }} .fz-seg button {
    border: 0; background: transparent; cursor: pointer; padding: 4px 0;
    font-size: 14px; font-weight: 500; line-height: 1.2;
    color: var(--fz-muted);
    border-bottom: 1.5px solid transparent;
    transition: color .2s ease, border-color .2s ease;
  }
  #shopify-section-{{ section.id }} .fz-seg button:hover { color: var(--fz-ink); }
  #shopify-section-{{ section.id }} .fz-seg button.is-active {
    color: var(--fz-ink); font-weight: 700;
    border-bottom-color: var(--fz-mint);
  }
  #shopify-section-{{ section.id }} .fz-seg-divider {
    width: 1px; height: 16px; background: var(--fz-line);
  }

  #shopify-section-{{ section.id }} .fz-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    column-gap: 22px;
    row-gap: 36px;
  }

  @media (min-width: 760px) {
    #shopify-section-{{ section.id }} .fz-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  }

  @media (min-width: 1120px) {
    #shopify-section-{{ section.id }} .fz-container { width: min(1120px, calc(100% - 32px)); }
  }

  #shopify-section-{{ section.id }} .fz-fade { opacity: 0; transition: opacity .55s ease; }
  #shopify-section-{{ section.id }} .fz-fade.is-in { opacity: 1; }

  /* the whole tile is the link — no card chrome */
  #shopify-section-{{ section.id }} .fz-tile {
    display: flex; flex-direction: column;
    text-decoration: none; color: inherit; min-width: 0;
  }
  #shopify-section-{{ section.id }} .fz-tile-media {
    position: relative;
    aspect-ratio: 1 / 1;
    width: 100%;
    border-radius: var(--fz-r-tile);
    overflow: hidden;
    background: var(--fz-tile);
    display: flex; align-items: center; justify-content: center;
  }
  #shopify-section-{{ section.id }} .fz-tile-media img {
    width: 100%; height: 100%;
    object-fit: contain;
    display: block;
    padding: 8px;
    opacity: 0;
    transition: opacity .35s ease, transform .45s var(--fz-ease);
  }
  #shopify-section-{{ section.id }} .fz-tile-media img.is-loaded { opacity: 1; }
  #shopify-section-{{ section.id }} .fz-tile:hover .fz-tile-media img.is-loaded { transform: scale(1.035); }
  #shopify-section-{{ section.id }} .fz-tile-fallback { font-size: 44px; opacity: .3; }

  /* badges sit lightly on the image */
  #shopify-section-{{ section.id }} .fz-pill {
    position: absolute; top: 12px;
    display: inline-flex; align-items: center; gap: 6px;
    padding: 7px 13px;
    border-radius: 999px;
    background: var(--fz-cream);
    color: var(--fz-ink);
    font-size: 12.5px; font-weight: 500; line-height: 1;
  }
  #shopify-section-{{ section.id }} .fz-pill-origin { inset-inline-end: 12px; }
  #shopify-section-{{ section.id }} .fz-pill-best {
    inset-inline-start: 12px;
    background: var(--fz-mint-soft);
    color: var(--fz-mint-deep);
    font-weight: 700;
  }
  #shopify-section-{{ section.id }} .fz-pill-flag { font-size: 14px; line-height: 1; }

  /* text under the tile — centered and quiet */
  #shopify-section-{{ section.id }} .fz-tile-body {
    display: flex; flex-direction: column; align-items: center; gap: 7px;
    padding: 16px 6px 0; text-align: center;
  }
  #shopify-section-{{ section.id }} .fz-tile-name {
    margin: 0;
    font-size: 16px; line-height: 1.4; font-weight: 500;
    letter-spacing: -.01em; color: var(--fz-ink);
    display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2;
    overflow: hidden;
  }
  #shopify-section-{{ section.id }} .fz-tile-price {
    font-size: 17px; line-height: 1.2; font-weight: 600;
    letter-spacing: -.01em; color: var(--fz-ink);
  }
  #shopify-section-{{ section.id }} .fz-tile-store {
    font-size: 13px; font-weight: 400; color: var(--fz-muted);
    max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }

  #shopify-section-{{ section.id }} .fz-empty {
    padding: 40px 18px; text-align: center;
    color: var(--fz-muted); font-size: 16px; line-height: 1.8;
  }
  #shopify-section-{{ section.id }} .fz-empty.fz-error { color: #a33d1c; }
  #shopify-section-{{ section.id }} .fz-empty .fz-chip {
    display: inline-block; margin: 8px 4px 0;
    border: 1px solid var(--fz-line); background: #fff;
    color: var(--fz-ink); border-radius: 999px;
    padding: 10px 16px; font-size: 14px; font-weight: 500; cursor: pointer;
    transition: border-color .2s ease, background .2s ease;
  }
  #shopify-section-{{ section.id }} .fz-empty .fz-chip:hover { border-color: var(--fz-mint); background: var(--fz-mint-soft); }

  @keyframes fzRail {
    0%   { transform: translateX(-120%); }
    100% { transform: translateX(420%); }
  }
  @keyframes fzFade { from { opacity: 0; } to { opacity: 1; } }

  @media (prefers-reduced-motion: reduce) {
    #shopify-section-{{ section.id }} .fz-search-card.is-busy .fz-rail::after { animation: none; opacity: .5; }
    #shopify-section-{{ section.id }} .fz-fade { transition-duration: .01s; }
  }

  /* ================= MOBILE ================= */
  @media (max-width: 720px) {
    #shopify-section-{{ section.id }} .fz-home { padding-top: 10px; }
    #shopify-section-{{ section.id }} .fz-container { width: calc(100% - 20px); }
    #shopify-section-{{ section.id }} .fz-topbar { padding: 10px 12px; margin-bottom: 12px; }
    #shopify-section-{{ section.id }} .fz-logo { max-width: 122px; }
    #shopify-section-{{ section.id }} .fz-lang-btn { padding: 8px 14px; font-size: 13px; }
    #shopify-section-{{ section.id }} .fz-search-card { padding: 14px; }
    #shopify-section-{{ section.id }} .fz-search-row { grid-template-columns: 1fr; }
    #shopify-section-{{ section.id }} .fz-btn { width: 100%; height: 60px; font-size: 17px; }
    #shopify-section-{{ section.id }} .fz-input { height: 66px; font-size: 16.5px; padding: 0 72px 0 48px; }
    #shopify-section-{{ section.id }} .fz-home:is([data-lang="ar"],[data-lang="ur"]) .fz-input { padding: 0 48px 0 72px; }
    #shopify-section-{{ section.id }} .fz-input-icon { left: 16px; }
    #shopify-section-{{ section.id }} .fz-home:is([data-lang="ar"],[data-lang="ur"]) .fz-input-icon { left: auto; right: 16px; }
    #shopify-section-{{ section.id }} .fz-photo-inline { width: 50px; height: 50px; right: 8px; }
    #shopify-section-{{ section.id }} .fz-home:is([data-lang="ar"],[data-lang="ur"]) .fz-photo-inline { right: auto; left: 8px; }

    #shopify-section-{{ section.id }} .fz-results-shell { margin-top: 28px; }
    #shopify-section-{{ section.id }} .fz-results-head { margin-bottom: 16px; }
    #shopify-section-{{ section.id }} .fz-grid { column-gap: 16px; row-gap: 30px; }
    #shopify-section-{{ section.id }} .fz-tile-media img { padding: 10px; }
    #shopify-section-{{ section.id }} .fz-tile-body { padding-top: 13px; gap: 5px; }
    #shopify-section-{{ section.id }} .fz-tile-name { font-size: 14.5px; }
    #shopify-section-{{ section.id }} .fz-tile-price { font-size: 15.5px; }
    #shopify-section-{{ section.id }} .fz-tile-store { font-size: 12px; }
    #shopify-section-{{ section.id }} .fz-pill { font-size: 11.5px; padding: 6px 11px; top: 10px; }
    #shopify-section-{{ section.id }} .fz-pill-origin { inset-inline-end: 10px; }
    #shopify-section-{{ section.id }} .fz-pill-best { inset-inline-start: 10px; }
    #shopify-section-{{ section.id }} .fz-seg button { font-size: 13.5px; }
    #shopify-section-{{ section.id }} .fz-controls { gap: 12px; }
  }

  /* ===== V24 · Minimal Premium Search UI ===== */
  #shopify-section-{{ section.id }} {
    --fz-ink:#121816; --fz-muted:#737d79; --fz-line:#e8ecea;
    --fz-page:#fbfcfb; --fz-soft:#f4f6f5; --fz-accent:#173f36;
    --fz-accent-soft:#edf4f1; --fz-coral:#ef6947;
    --fz-shadow:0 18px 44px -28px rgba(18,24,22,.22);
  }

  #shopify-section-{{ section.id }} .fz-home {
    background:var(--fz-page); padding:10px 0 56px;
  }
  #shopify-section-{{ section.id }} .fz-container {
    width:min(1040px,calc(100% - 24px));
  }

  #shopify-section-{{ section.id }} .fz-topbar {
    padding:8px 2px; margin-bottom:18px;
    border:0; border-radius:0; background:transparent;
    box-shadow:none; backdrop-filter:none;
  }
  #shopify-section-{{ section.id }} .fz-logo { max-width:132px; }

  #shopify-section-{{ section.id }} .fz-lang-toggle {
    padding:3px; border-radius:999px; background:#f0f2f1;
    border:1px solid #e5e9e7;
  }
  #shopify-section-{{ section.id }} .fz-lang-btn {
    padding:8px 14px; font-size:12.5px; color:#7a8581;
  }
  #shopify-section-{{ section.id }} .fz-lang-btn.is-active {
    background:var(--fz-ink); color:#fff;
  }

  #shopify-section-{{ section.id }} .fz-search-card {
    max-width:860px; padding:0; margin:0 auto;
    border:0; border-radius:0; background:transparent;
    box-shadow:none; overflow:visible;
  }
  #shopify-section-{{ section.id }} .fz-rail { display:none; }

  #shopify-section-{{ section.id }} .fz-search-row {
    grid-template-columns:minmax(0,1fr) auto; gap:10px;
  }
  #shopify-section-{{ section.id }} .fz-input {
    height:64px; border-radius:18px;
    border:1px solid #e1e6e3; background:#fff;
    font-size:17px; padding-inline-start:48px; padding-inline-end:68px;
    box-shadow:var(--fz-shadow);
  }
  #shopify-section-{{ section.id }} .fz-input:focus {
    border-color:#b8c6c0;
    box-shadow:0 0 0 4px rgba(23,63,54,.06),var(--fz-shadow);
  }
  #shopify-section-{{ section.id }} .fz-input-icon {
    color:#81908b; left:17px;
  }
  #shopify-section-{{ section.id }} .fz-home:is([data-lang="ar"],[data-lang="ur"]) .fz-input-icon {
    left:auto; right:17px;
  }

  #shopify-section-{{ section.id }} .fz-photo-inline {
    width:46px; height:46px; right:9px; border-radius:14px;
    background:var(--fz-accent-soft); color:var(--fz-accent); box-shadow:none;
  }
  #shopify-section-{{ section.id }} .fz-home:is([data-lang="ar"],[data-lang="ur"]) .fz-photo-inline {
    right:auto; left:9px;
  }
  #shopify-section-{{ section.id }} .fz-photo-inline::after {
    width:8px; height:8px; top:-1px; inset-inline-end:-1px;
    border-radius:50%; border:1.5px solid #fff; background:var(--fz-coral);
  }

  #shopify-section-{{ section.id }} .fz-btn {
    height:64px; border-radius:18px; padding:0 28px; font-size:16px;
  }
  #shopify-section-{{ section.id }} .fz-btn-primary {
    min-width:132px; background:var(--fz-ink); box-shadow:var(--fz-shadow);
  }

  #shopify-section-{{ section.id }} .fz-wa-row { margin-top:10px; }
  #shopify-section-{{ section.id }} .fz-wa-btn {
    padding:8px 12px; background:transparent; border:0;
    color:#77817d; font-size:13px;
  }
  #shopify-section-{{ section.id }} .fz-status {
    margin-top:10px; font-size:13px; color:#7c8783;
  }

  #shopify-section-{{ section.id }} .fz-results-shell { margin-top:42px; }
  #shopify-section-{{ section.id }} .fz-results-head {
    align-items:flex-end; margin-bottom:18px;
  }
  #shopify-section-{{ section.id }} .fz-results-title {
    font-family:var(--fz-font)!important;
    font-size:clamp(24px,4vw,34px);
    font-weight:700; line-height:1.15; letter-spacing:-.03em;
  }
  #shopify-section-{{ section.id }} .fz-results-title span {
    display:block; margin:5px 0 0; font-size:12px;
    font-weight:500; color:#8a9490;
  }

  #shopify-section-{{ section.id }} .fz-controls {
    gap:8px; width:100%; margin-top:4px;
  }
  #shopify-section-{{ section.id }} .fz-seg {
    gap:6px; flex-wrap:wrap;
  }
  #shopify-section-{{ section.id }} .fz-seg-divider { display:none; }
  #shopify-section-{{ section.id }} .fz-seg button {
    padding:8px 12px; border-radius:999px;
    border:1px solid transparent; background:transparent;
    color:#7c8682; font-size:12.5px; font-weight:600;
  }
  #shopify-section-{{ section.id }} .fz-seg button.is-active {
    background:#fff; border-color:#dde3e0; color:var(--fz-ink);
    box-shadow:0 4px 12px -10px rgba(18,24,22,.28);
  }

  #shopify-section-{{ section.id }} .fz-grid {
    grid-template-columns:repeat(2,minmax(0,1fr));
    column-gap:16px; row-gap:28px;
  }

  #shopify-section-{{ section.id }} .fz-tile-media {
    border-radius:20px; background:#f2f4f3; border:1px solid #edf0ee;
  }
  #shopify-section-{{ section.id }} .fz-tile-media img {
    object-fit:contain; padding:12px; background:#f8f9f8;
  }

  #shopify-section-{{ section.id }} .fz-pill {
    top:10px; padding:6px 10px; border-radius:999px;
    background:rgba(255,255,255,.92); color:#4b5551;
    font-size:11px; font-weight:600;
    box-shadow:0 4px 14px -10px rgba(18,24,22,.35);
    backdrop-filter:blur(8px);
  }
  #shopify-section-{{ section.id }} .fz-pill-best {
    background:#eef6f2; color:#255e4f;
  }

  #shopify-section-{{ section.id }} .fz-tile-body {
    align-items:flex-start; text-align:start; gap:4px; padding:10px 2px 0;
  }
  #shopify-section-{{ section.id }} .fz-tile-store {
    order:1; font-size:11.5px; font-weight:600; color:#89938f;
  }
  #shopify-section-{{ section.id }} .fz-tile-name {
    order:2; font-size:14.5px; line-height:1.35;
    font-weight:600; letter-spacing:-.012em;
    color:#1b2320; min-height:2.7em;
  }
  #shopify-section-{{ section.id }} .fz-tile-price {
    order:3; font-size:15.5px; line-height:1.25;
    font-weight:700; color:#161d1a;
  }

  @media (min-width:860px) {
    #shopify-section-{{ section.id }} .fz-grid {
      grid-template-columns:repeat(3,minmax(0,1fr));
      column-gap:20px; row-gap:32px;
    }
  }

  @media (max-width:720px) {
    #shopify-section-{{ section.id }} .fz-home { padding-top:8px; }
    #shopify-section-{{ section.id }} .fz-container { width:calc(100% - 18px); }
    #shopify-section-{{ section.id }} .fz-topbar {
      padding:4px 0 10px; margin-bottom:10px;
    }
    #shopify-section-{{ section.id }} .fz-logo { max-width:116px; }
    #shopify-section-{{ section.id }} .fz-search-row {
      grid-template-columns:1fr; gap:8px;
    }
    #shopify-section-{{ section.id }} .fz-input {
      height:60px; border-radius:16px; font-size:15.5px;
    }
    #shopify-section-{{ section.id }} .fz-photo-inline {
      width:44px; height:44px; border-radius:13px; right:8px;
    }
    #shopify-section-{{ section.id }} .fz-home:is([data-lang="ar"],[data-lang="ur"]) .fz-photo-inline {
      right:auto; left:8px;
    }
    #shopify-section-{{ section.id }} .fz-btn {
      height:54px; border-radius:16px; font-size:15.5px;
    }
    #shopify-section-{{ section.id }} .fz-results-shell { margin-top:30px; }
    #shopify-section-{{ section.id }} .fz-results-title { font-size:25px; }
    #shopify-section-{{ section.id }} .fz-grid {
      column-gap:12px; row-gap:24px;
    }
    #shopify-section-{{ section.id }} .fz-tile-media { border-radius:18px; }
    #shopify-section-{{ section.id }} .fz-tile-media img { padding:8px; }
    #shopify-section-{{ section.id }} .fz-tile-body {
      padding-top:8px; gap:3px;
    }
    #shopify-section-{{ section.id }} .fz-tile-name {
      font-size:13.5px; min-height:2.65em;
    }
    #shopify-section-{{ section.id }} .fz-tile-price { font-size:14.5px; }
    #shopify-section-{{ section.id }} .fz-tile-store { font-size:11px; }
  }


  /* ===== V25 · stay-put search + magical skeleton loading ===== */
  #shopify-section-{{ section.id }} .fz-magic-loading {
    display:grid;
    grid-template-columns:repeat(2,minmax(0,1fr));
    gap:24px 12px;
    margin-top:4px;
  }

  #shopify-section-{{ section.id }} .fz-magic-card {
    min-width:0;
  }

  #shopify-section-{{ section.id }} .fz-magic-media {
    position:relative;
    aspect-ratio:1 / 1;
    border-radius:18px;
    overflow:hidden;
    background:
      radial-gradient(circle at 28% 26%, rgba(255,255,255,.96) 0 7%, transparent 8%),
      linear-gradient(120deg, #f1f4f2 8%, #f8faf9 28%, #eef3f0 46%, #fafcfb 66%, #f0f3f1 84%);
    background-size:220% 100%;
    border:1px solid #edf1ef;
    animation:fzMagicShimmer 1.6s ease-in-out infinite;
  }

  #shopify-section-{{ section.id }} .fz-magic-media::before,
  #shopify-section-{{ section.id }} .fz-magic-media::after {
    content:'';
    position:absolute;
    border-radius:999px;
    pointer-events:none;
  }

  #shopify-section-{{ section.id }} .fz-magic-media::before {
    width:10px;
    height:10px;
    top:22%;
    left:24%;
    background:rgba(69,207,161,.70);
    box-shadow:
      46px 26px 0 -2px rgba(239,105,71,.55),
      82px -8px 0 -3px rgba(69,207,161,.35),
      108px 58px 0 -4px rgba(18,24,22,.20);
    animation:fzMagicFloat 2.2s ease-in-out infinite;
  }

  #shopify-section-{{ section.id }} .fz-magic-media::after {
    inset:0;
    background:linear-gradient(
      110deg,
      transparent 28%,
      rgba(255,255,255,0) 38%,
      rgba(255,255,255,.85) 48%,
      rgba(255,255,255,0) 58%,
      transparent 72%
    );
    transform:translateX(-120%);
    animation:fzMagicSweep 1.9s cubic-bezier(.4,0,.2,1) infinite;
  }

  #shopify-section-{{ section.id }} .fz-magic-lines {
    padding:10px 2px 0;
  }

  #shopify-section-{{ section.id }} .fz-magic-line {
    height:10px;
    margin-bottom:7px;
    border-radius:999px;
    background:linear-gradient(90deg,#edf1ef,#f7f9f8,#edf1ef);
    background-size:200% 100%;
    animation:fzMagicShimmer 1.7s ease-in-out infinite;
  }

  #shopify-section-{{ section.id }} .fz-magic-line:nth-child(1) { width:42%; height:8px; }
  #shopify-section-{{ section.id }} .fz-magic-line:nth-child(2) { width:92%; }
  #shopify-section-{{ section.id }} .fz-magic-line:nth-child(3) { width:58%; height:12px; }

  #shopify-section-{{ section.id }} .fz-magic-caption {
    display:flex;
    align-items:center;
    gap:8px;
    margin:0 0 14px;
    color:#7d8884;
    font-size:12.5px;
    font-weight:600;
  }

  #shopify-section-{{ section.id }} .fz-magic-orb {
    width:8px;
    height:8px;
    border-radius:50%;
    background:var(--fz-accent);
    box-shadow:0 0 0 0 rgba(23,63,54,.18);
    animation:fzMagicPulse 1.5s ease-out infinite;
  }

  @keyframes fzMagicShimmer {
    0% { background-position:200% 0; }
    100% { background-position:-40% 0; }
  }

  @keyframes fzMagicSweep {
    0% { transform:translateX(-120%); opacity:.0; }
    22% { opacity:1; }
    72% { opacity:.65; }
    100% { transform:translateX(120%); opacity:0; }
  }

  @keyframes fzMagicFloat {
    0%,100% { transform:translate3d(0,0,0) scale(.9); opacity:.6; }
    50% { transform:translate3d(10px,-8px,0) scale(1.12); opacity:1; }
  }

  @keyframes fzMagicPulse {
    0% { box-shadow:0 0 0 0 rgba(23,63,54,.20); opacity:.75; }
    70% { box-shadow:0 0 0 8px rgba(23,63,54,0); opacity:1; }
    100% { box-shadow:0 0 0 0 rgba(23,63,54,0); opacity:.75; }
  }

  @media (min-width:860px) {
    #shopify-section-{{ section.id }} .fz-magic-loading {
      grid-template-columns:repeat(3,minmax(0,1fr));
      gap:30px 20px;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    #shopify-section-{{ section.id }} .fz-magic-media,
    #shopify-section-{{ section.id }} .fz-magic-media::before,
    #shopify-section-{{ section.id }} .fz-magic-media::after,
    #shopify-section-{{ section.id }} .fz-magic-line,
    #shopify-section-{{ section.id }} .fz-magic-orb {
      animation:none !important;
    }
  }

</style>

<section class="fz-home" id="findzia-home-{{ section.id }}" data-lang="en" dir="ltr">
  <div class="fz-container">

    <div class="fz-topbar">
      <div class="fz-logo-wrap">
        {% if section.settings.logo != blank %}
          <img class="fz-logo" src="{{ section.settings.logo | image_url: width: 400 }}" alt="Findzia" loading="eager">
        {% else %}
          <div class="fz-logo-fallback">FIND<em>ZIA</em></div>
        {% endif %}
      </div>
      <div class="fz-lang-toggle" aria-label="Language">
        <button class="fz-lang-btn" type="button" data-lang-btn="local" data-local-lang-btn>عربي</button>
        <button class="fz-lang-btn is-active" type="button" data-lang-btn="en">EN</button>
      </div>
    </div>

    <div class="fz-search-card" data-search-card>
      <div class="fz-rail" aria-hidden="true"></div>

      <div class="fz-search-row">
        <div class="fz-input-wrap">
          <svg class="fz-input-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"></circle>
            <path d="M20 20L17 17" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path>
          </svg>
          <input class="fz-input" id="fz-query-{{ section.id }}" type="text"
                 placeholder="Search by product name or photo" autocomplete="off">
          <input id="fz-photo-{{ section.id }}" type="file" accept="image/jpeg,image/png,image/webp" hidden>
          <button class="fz-photo-inline" type="button" data-photo-btn aria-label="Search by photo" title="Search by photo">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <rect x="3.5" y="6" width="17" height="13" rx="3" stroke="currentColor" stroke-width="1.9"/>
              <path d="M8 6l1.3-2h5.4L16 6" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>
              <circle cx="12" cy="12.5" r="3.3" stroke="currentColor" stroke-width="1.9"/>
            </svg>
          </button>
        </div>
        <button class="fz-btn fz-btn-primary" type="button" data-search-btn>
          <span data-i18n="search_btn">Search</span>
        </button>
      </div>

      <div class="fz-status" data-status>Searching stores…</div>

      <div class="fz-wa-row">
        <a class="fz-wa-btn" href="#" data-wa-link target="_blank" rel="noopener">
          <svg class="fz-wa-icon" viewBox="0 0 32 32" aria-hidden="true">
            <path fill="#25D366" d="M16 3.2C8.9 3.2 3.2 8.9 3.2 16c0 2.3.6 4.5 1.7 6.4L3 29l6.8-1.8c1.9 1 4 1.6 6.2 1.6 7.1 0 12.8-5.7 12.8-12.8S23.1 3.2 16 3.2z"/>
            <path fill="#fff" d="M22.3 19c-.3-.2-1.9-1-2.2-1.1-.3-.1-.5-.2-.7.2s-.8 1-1 1.2c-.2.2-.4.2-.7.1-.3-.2-1.4-.5-2.6-1.6-1-.9-1.6-1.9-1.8-2.3-.2-.3 0-.5.1-.7l.5-.6c.2-.2.2-.3.3-.6 0-.2 0-.4-.1-.6l-1-2.3c-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.6.1-.9.4-.3.4-1.2 1.2-1.2 2.8s1.2 3.3 1.4 3.5c.2.2 2.4 3.7 5.8 5.1 2.9 1.1 3.4.9 4.1.9.6-.1 1.9-.8 2.2-1.5.3-.8.3-1.4.2-1.5-.1-.2-.3-.3-.6-.4z"/>
          </svg>
          <span data-i18n="wa_alt">Or search on WhatsApp</span>
        </a>
      </div>
    </div>

    <div class="fz-results-shell" data-results-shell aria-live="polite">
      <div class="fz-results-head">
        <h2 class="fz-results-title" data-results-title></h2>
        <div class="fz-controls">
          <div class="fz-seg" data-filter-seg>
            <button type="button" data-filter="all" class="is-active" data-i18n="f_all">All</button>
            <button type="button" data-filter="local" data-local-label>Kuwait</button>
            <button type="button" data-filter="global" data-i18n="f_global">Global</button>
          </div>
          <span class="fz-seg-divider" aria-hidden="true"></span>
          <div class="fz-seg" data-sort-seg>
            <button type="button" data-sort="relevance" class="is-active" data-i18n="s_best">Best match</button>
            <button type="button" data-sort="price" data-i18n="s_price">Lowest price</button>
          </div>
        </div>
      </div>
      <div data-results-body></div>
    </div>

  </div>
</section>

<script>
  (function() {
    var section = document.getElementById('findzia-home-{{ section.id }}');
    if (!section) return;

    var apiBase = {{ section.settings.api_base_url | json }} || '';
    var whatsappNumber = {{ section.settings.whatsapp_number | json }} || '';
    var shopifyCountry = ({{ localization.country.iso_code | default: 'KW' | json }} || 'KW').toUpperCase();
    var shopifyCountryName = {{ localization.country.name | default: 'Local' | json }} || 'Local';
    var marketCountry = shopifyCountry;
    var marketCountryName = shopifyCountryName;
    var marketCountryReady = false;
    var geoStorageKey = 'findzia-market-country-v1';
    var geoNameStorageKey = 'findzia-market-country-name-v1';
    var geoStorageTsKey = 'findzia-market-country-ts-v1';
    var storageKey = 'findzia-lang';

    var searchCard = section.querySelector('[data-search-card]');
    var langButtons = [].slice.call(section.querySelectorAll('[data-lang-btn]'));
    var searchButtons = [].slice.call(section.querySelectorAll('[data-search-btn]'));
    var queryInput = section.querySelector('#fz-query-{{ section.id }}');
    var photoButton = section.querySelector('[data-photo-btn]');
    var photoInput = section.querySelector('#fz-photo-{{ section.id }}');
    var waLink = section.querySelector('[data-wa-link]');
    var resultsShell = section.querySelector('[data-results-shell]');
    var resultsBody = section.querySelector('[data-results-body]');
    var resultsTitle = section.querySelector('[data-results-title]');
    var statusEl = section.querySelector('[data-status]');
    var filterSeg = section.querySelector('[data-filter-seg]');
    var sortSeg = section.querySelector('[data-sort-seg]');

    var renderToken = 0;
    var items = [];
    var itemIndex = {};
    var seenKeys = {};
    var activeFilter = 'all';
    var activeSort = 'relevance';
    var renderScheduled = false;
    var lastQuery = '';
    var showingMagicLoading = false;

    var dict = {
      en: {
        search_btn:'Search', wa_alt:'Or search on WhatsApp',
        placeholder:'Search by product name or photo',
        searching:'Searching stores…', searching_image:'Reading the image and finding matches…',
        magic_text:'Searching stores and finding the closest matches…',
        magic_image:'Reading your photo and searching stores…',
        results_for:'Results', results_photo:'Results',
        count_one:'result', count_many:'results',
        f_all:'All', f_global:'Global',
        s_best:'Best match', s_price:'Lowest price',
        best_price:'Lowest', fallback_price:'Price at store',
        no_results:'Nothing matched that search. Try a different product name or a clearer photo.',
        no_filter:'No results in this filter.',
        error_text:'The search did not complete. Try again.',
        error_image:'The image search did not complete. Try another photo or type the name.'
      },
      ar: {
        search_btn:'ابحث', wa_alt:'أو ابحث عبر واتساب',
        placeholder:'ابحث باسم المنتج أو بالصورة',
        searching:'جارٍ البحث في المتاجر…', searching_image:'جارٍ تحليل الصورة والبحث عن المطابقات…',
        magic_text:'أبحث بين المتاجر وألتقط أفضل التطابقات…',
        magic_image:'أحلّل الصورة وأبحث بين المتاجر…',
        results_for:'النتائج', results_photo:'النتائج',
        count_one:'نتيجة', count_many:'نتيجة',
        f_all:'الكل', f_global:'عالمي',
        s_best:'الأنسب', s_price:'الأقل سعراً',
        best_price:'الأقل', fallback_price:'السعر لدى المتجر',
        no_results:'ما لقينا نتيجة مطابقة. جرّب اسم منتج ثاني أو صورة أوضح.',
        no_filter:'لا توجد نتائج ضمن هذا التصنيف.',
        error_text:'ما اكتمل البحث. حاول مرة ثانية.',
        error_image:'ما اكتمل البحث بالصورة. جرّب صورة ثانية أو اكتب الاسم.'
      },
      de: {
        search_btn:'Suchen', wa_alt:'Oder über WhatsApp suchen',
        placeholder:'Nach Produktname oder Foto suchen',
        searching:'Shops werden durchsucht…', searching_image:'Foto wird analysiert und passende Produkte werden gesucht…',
        magic_text:'Shops werden durchsucht und passende Treffer gefunden…',
        magic_image:'Foto wird analysiert und Shops werden durchsucht…',
        results_for:'Ergebnisse', results_photo:'Ergebnisse',
        count_one:'Ergebnis', count_many:'Ergebnisse',
        f_all:'Alle', f_global:'Global',
        s_best:'Beste Treffer', s_price:'Niedrigster Preis',
        best_price:'Günstigster', fallback_price:'Preis im Shop',
        no_results:'Keine passenden Ergebnisse. Versuche einen anderen Produktnamen oder ein klareres Foto.',
        no_filter:'Keine Ergebnisse in diesem Filter.',
        error_text:'Die Suche konnte nicht abgeschlossen werden. Bitte erneut versuchen.',
        error_image:'Die Bildsuche konnte nicht abgeschlossen werden.'
      },
      fr: {
        search_btn:'Rechercher', wa_alt:'Ou rechercher sur WhatsApp',
        placeholder:'Rechercher par nom de produit ou photo',
        searching:'Recherche dans les boutiques…', searching_image:'Analyse de la photo et recherche des correspondances…',
        magic_text:'Recherche dans les boutiques des meilleures correspondances…',
        magic_image:'Analyse de votre photo et recherche dans les boutiques…',
        results_for:'Résultats', results_photo:'Résultats',
        count_one:'résultat', count_many:'résultats',
        f_all:'Tous', f_global:'Global',
        s_best:'Meilleure correspondance', s_price:'Prix le plus bas',
        best_price:'Le moins cher', fallback_price:'Prix en boutique',
        no_results:'Aucun résultat correspondant.', no_filter:'Aucun résultat dans ce filtre.',
        error_text:'La recherche n’a pas pu être terminée.', error_image:'La recherche par image n’a pas pu être terminée.'
      },
      es: {
        search_btn:'Buscar', wa_alt:'O buscar por WhatsApp',
        placeholder:'Buscar por nombre del producto o foto',
        searching:'Buscando en tiendas…', searching_image:'Analizando la foto y buscando coincidencias…',
        magic_text:'Buscando en tiendas las mejores coincidencias…',
        magic_image:'Analizando tu foto y buscando en tiendas…',
        results_for:'Resultados', results_photo:'Resultados',
        count_one:'resultado', count_many:'resultados',
        f_all:'Todo', f_global:'Global',
        s_best:'Mejor coincidencia', s_price:'Precio más bajo',
        best_price:'Más barato', fallback_price:'Precio en tienda',
        no_results:'No encontramos resultados coincidentes.', no_filter:'No hay resultados en este filtro.',
        error_text:'La búsqueda no pudo completarse.', error_image:'La búsqueda por imagen no pudo completarse.'
      },
      pt: {
        search_btn:'Pesquisar', wa_alt:'Ou pesquisar no WhatsApp',
        placeholder:'Pesquisar por nome do produto ou foto',
        searching:'Pesquisando lojas…', searching_image:'Analisando a foto e procurando correspondências…',
        magic_text:'Pesquisando lojas e encontrando as melhores correspondências…',
        magic_image:'Analisando sua foto e pesquisando lojas…',
        results_for:'Resultados', results_photo:'Resultados',
        count_one:'resultado', count_many:'resultados',
        f_all:'Todos', f_global:'Global',
        s_best:'Melhor resultado', s_price:'Menor preço',
        best_price:'Menor', fallback_price:'Preço na loja',
        no_results:'Nenhum resultado correspondente.', no_filter:'Nenhum resultado neste filtro.',
        error_text:'A pesquisa não foi concluída.', error_image:'A pesquisa por imagem não foi concluída.'
      },
      tr: {
        search_btn:'Ara', wa_alt:'Veya WhatsApp’ta ara',
        placeholder:'Ürün adı veya fotoğrafla ara',
        searching:'Mağazalar aranıyor…', searching_image:'Fotoğraf analiz ediliyor ve eşleşmeler aranıyor…',
        magic_text:'Mağazalar taranıyor ve en yakın eşleşmeler bulunuyor…',
        magic_image:'Fotoğrafınız analiz ediliyor ve mağazalar aranıyor…',
        results_for:'Sonuçlar', results_photo:'Sonuçlar',
        count_one:'sonuç', count_many:'sonuç',
        f_all:'Tümü', f_global:'Global',
        s_best:'En iyi eşleşme', s_price:'En düşük fiyat',
        best_price:'En düşük', fallback_price:'Mağaza fiyatı',
        no_results:'Eşleşen sonuç bulunamadı.', no_filter:'Bu filtrede sonuç yok.',
        error_text:'Arama tamamlanamadı.', error_image:'Görsel arama tamamlanamadı.'
      },
      ru: {
        search_btn:'Поиск', wa_alt:'Или искать в WhatsApp',
        placeholder:'Поиск по названию товара или фото',
        searching:'Поиск по магазинам…', searching_image:'Анализ фото и поиск совпадений…',
        magic_text:'Ищем по магазинам лучшие совпадения…',
        magic_image:'Анализируем фото и ищем по магазинам…',
        results_for:'Результаты', results_photo:'Результаты',
        count_one:'результат', count_many:'результатов',
        f_all:'Все', f_global:'Глобально',
        s_best:'Лучшее совпадение', s_price:'Самая низкая цена',
        best_price:'Дешевле', fallback_price:'Цена в магазине',
        no_results:'Подходящих результатов не найдено.', no_filter:'В этом фильтре нет результатов.',
        error_text:'Поиск не завершён.', error_image:'Поиск по изображению не завершён.'
      },
      zh: {
        search_btn:'搜索', wa_alt:'或通过 WhatsApp 搜索',
        placeholder:'按商品名称或图片搜索',
        searching:'正在搜索商店…', searching_image:'正在分析图片并寻找匹配商品…',
        magic_text:'正在搜索商店并寻找最佳匹配…',
        magic_image:'正在分析图片并搜索商店…',
        results_for:'搜索结果', results_photo:'搜索结果',
        count_one:'个结果', count_many:'个结果',
        f_all:'全部', f_global:'全球',
        s_best:'最佳匹配', s_price:'最低价格',
        best_price:'最低', fallback_price:'店内价格',
        no_results:'没有找到匹配结果。', no_filter:'此筛选条件下没有结果。',
        error_text:'搜索未能完成。', error_image:'图片搜索未能完成。'
      },
      hi: {
        search_btn:'खोजें', wa_alt:'या WhatsApp पर खोजें',
        placeholder:'उत्पाद नाम या फोटो से खोजें',
        searching:'स्टोर्स में खोज रहे हैं…', searching_image:'फोटो पढ़कर मिलते-जुलते उत्पाद खोज रहे हैं…',
        magic_text:'स्टोर्स में सबसे अच्छे मिलान खोज रहे हैं…',
        magic_image:'आपकी फोटो पढ़कर स्टोर्स में खोज रहे हैं…',
        results_for:'परिणाम', results_photo:'परिणाम',
        count_one:'परिणाम', count_many:'परिणाम',
        f_all:'सभी', f_global:'ग्लोबल',
        s_best:'सबसे अच्छा मिलान', s_price:'सबसे कम कीमत',
        best_price:'सबसे कम', fallback_price:'स्टोर पर कीमत',
        no_results:'कोई मिलान नहीं मिला।', no_filter:'इस फ़िल्टर में कोई परिणाम नहीं है।',
        error_text:'खोज पूरी नहीं हो सकी।', error_image:'इमेज खोज पूरी नहीं हो सकी।'
      },
      ur: {
        search_btn:'تلاش', wa_alt:'یا WhatsApp پر تلاش کریں',
        placeholder:'پروڈکٹ کے نام یا تصویر سے تلاش کریں',
        searching:'اسٹورز میں تلاش جاری ہے…', searching_image:'تصویر کا تجزیہ اور مماثلتیں تلاش کی جا رہی ہیں…',
        magic_text:'اسٹورز میں بہترین مماثلتیں تلاش کی جا رہی ہیں…',
        magic_image:'آپ کی تصویر کا تجزیہ کر کے اسٹورز میں تلاش جاری ہے…',
        results_for:'نتائج', results_photo:'نتائج',
        count_one:'نتیجہ', count_many:'نتائج',
        f_all:'سب', f_global:'عالمی',
        s_best:'بہترین مماثلت', s_price:'کم ترین قیمت',
        best_price:'کم ترین', fallback_price:'اسٹور پر قیمت',
        no_results:'کوئی مماثل نتیجہ نہیں ملا۔', no_filter:'اس فلٹر میں کوئی نتیجہ نہیں۔',
        error_text:'تلاش مکمل نہیں ہو سکی۔', error_image:'تصویری تلاش مکمل نہیں ہو سکی۔'
      }
    };

    var activeLang = 'en';
    var localLangCode = 'en';

    var countryLanguageMap = {
      KW:'ar', SA:'ar', AE:'ar', QA:'ar', BH:'ar', OM:'ar', JO:'ar', LB:'ar', IQ:'ar', YE:'ar',
      EG:'ar', LY:'ar', TN:'ar', DZ:'ar', MA:'ar', SD:'ar', SY:'ar', PS:'ar',
      DE:'de', AT:'de',
      FR:'fr', MC:'fr',
      ES:'es', MX:'es', AR:'es', CL:'es', CO:'es', PE:'es', VE:'es', EC:'es', UY:'es', PY:'es', BO:'es',
      PT:'pt', BR:'pt',
      TR:'tr',
      RU:'ru', BY:'ru',
      CN:'zh', TW:'zh', HK:'zh', MO:'zh',
      IN:'hi',
      PK:'ur'
    };

    var languageLabels = {
      ar:'عربي', de:'DE', fr:'FR', es:'ES', pt:'PT', tr:'TR', ru:'RU',
      zh:'中文', hi:'हिंदी', ur:'اردو', en:'EN'
    };

    function localLanguageForCountry(cc) {
      return countryLanguageMap[String(cc || '').toUpperCase()] || 'en';
    }

    function lang() { return activeLang || 'en'; }
    function t(k) { return (dict[lang()] && dict[lang()][k]) || dict.en[k] || k; }

    function updateLanguageToggle(countryChanged) {
      localLangCode = localLanguageForCountry(marketCountry || shopifyCountry);
      var localBtn = section.querySelector('[data-local-lang-btn]');
      var enBtn = section.querySelector('[data-lang-btn="en"]');

      if (localBtn) {
        localBtn.setAttribute('data-lang-btn', localLangCode);
        localBtn.textContent = languageLabels[localLangCode] || localLangCode.toUpperCase();
        localBtn.hidden = localLangCode === 'en';
      }

      if (enBtn) enBtn.hidden = false;
      langButtons = [].slice.call(section.querySelectorAll('[data-lang-btn]:not([hidden])'));

      var saved = '';
      try { saved = localStorage.getItem(storageKey) || ''; } catch(e) {}

      // If user explicitly chose English, preserve it. If the old saved language
      // belonged to another country (e.g. AR -> Germany), switch to the new local language.
      var desired = activeLang;
      if (countryChanged && desired !== 'en' && desired !== localLangCode) {
        desired = localLangCode;
      }
      if (!desired || (desired !== 'en' && desired !== localLangCode)) {
        desired = (saved === 'en' || saved === localLangCode) ? saved : localLangCode;
      }
      if (localLangCode === 'en') desired = 'en';
      applyLang(desired, true);
    }

    function safeUrl(v) {
      try {
        var u = new URL(String(v || ''), window.location.origin);
        return (u.protocol === 'http:' || u.protocol === 'https:') ? u.href : '';
      } catch (e) { return ''; }
    }
    function esc(s) {
      return String(s || '').replace(/[&<>"']/g, function(m) {
        return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'})[m];
      });
    }
    function waUrl() {
      var q = (queryInput && queryInput.value || '').trim();
      return whatsappNumber
        ? 'https://wa.me/' + encodeURIComponent(whatsappNumber) + (q ? '?text=' + encodeURIComponent(q) : '')
        : '#';
    }

    function applyLang(l, fromAuto) {
      l = dict[l] ? l : 'en';
      activeLang = l;
      var rtl = (l === 'ar' || l === 'ur');
      section.setAttribute('data-lang', l);
      section.setAttribute('dir', rtl ? 'rtl' : 'ltr');

      langButtons = [].slice.call(section.querySelectorAll('[data-lang-btn]:not([hidden])'));
      langButtons.forEach(function(b){
        b.classList.toggle('is-active', b.getAttribute('data-lang-btn') === l);
      });

      section.querySelectorAll('[data-i18n]').forEach(function(n){
        var k = n.getAttribute('data-i18n');
        n.textContent = t(k);
      });

      if (queryInput) queryInput.placeholder = t('placeholder');
      if (statusEl && !statusEl.classList.contains('is-visible')) statusEl.textContent = t('searching');
      updateLocalFilterLabel();
      if (waLink) waLink.href = waUrl();
      try { localStorage.setItem(storageKey, l); } catch (e) {}
      if (items.length) renderGrid();
    }

    function setBusy(on, message) {
      if (searchCard) searchCard.classList.toggle('is-busy', !!on);
      if (statusEl) {
        statusEl.classList.toggle('is-visible', !!on);
        if (on) statusEl.textContent = message || t('searching');
      }
      searchButtons.forEach(function(b){ b.disabled = !!on; });
    }

    function flagFor(item) {
      if (item && item.flag) return String(item.flag);
      if (!item) return '';
      if (item.market === 'local') return '🇰🇼';
      if (item.market === 'us') return '🇺🇸';
      if (item.market === 'china') return '🇨🇳';
      return '';
    }

    function escapeRe(v) { return String(v || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

    function smartTitle(item) {
      var title = String((item && item.title) || '').replace(/\s+/g, ' ').trim();
      var store = String((item && item.store) || '').replace(/\s+/g, ' ').trim();
      if (!title) return '';
      if (store) title = title.replace(new RegExp('^' + escapeRe(store) + '\\s*[-—–|:]+\\s*', 'i'), '');
      title = title.replace(/[|]+/g, ' — ').replace(/\s{2,}/g, ' ').trim();
      if (title.length > 62) title = title.slice(0, 62).replace(/\s+\S*$/, '').trim() + '…';
      return title;
    }

    function priceNumber(v) {
      var s = String(v || '').replace(/,/g, '');
      var m = s.match(/(\d+(?:\.\d+)?)/);
      return m ? Number(m[1]) : NaN;
    }

    function plausible(item) {
      var p = String((item && item.price) || '');
      var n = priceNumber(p);
      if (!Number.isFinite(n)) return true;
      var u = p.toUpperCase();
      if (u.indexOf('KWD') >= 0 && n > 10000) return false;
      if (u.indexOf('USD') >= 0 && n > 100000) return false;
      if ((u.indexOf('CNY') >= 0 || p.indexOf('¥') >= 0) && n > 1000000) return false;
      return n > 0;
    }

    function keyOf(item) {
      return String((item && item.url) || '').trim() ||
             [item && item.market, item && item.store, item && item.title].join('|');
    }

    function visibleItems() {
      var list = items.filter(function(it) {
        if (activeFilter === 'local') return it.market === 'local';
        if (activeFilter === 'global') return it.market !== 'local';
        return true;
      });
      if (activeSort === 'price') {
        list = list.slice().sort(function(a, b) {
          var na = priceNumber(a.price), nb = priceNumber(b.price);
          if (!Number.isFinite(na)) return 1;
          if (!Number.isFinite(nb)) return -1;
          return na - nb;
        });
      }
      return list;
    }

    function bestLocalKey() {
      var best = null, bestN = Infinity;
      items.forEach(function(it) {
        if (it.market !== 'local') return;
        var n = priceNumber(it.price);
        if (Number.isFinite(n) && n < bestN) { bestN = n; best = keyOf(it); }
      });
      return best;
    }

    function tileHtml(item, isBest) {
      var image = safeUrl(item.image || '');
      var url = safeUrl(item.url || '');
      var flag = flagFor(item);
      var name = smartTitle(item) || item.title || '';
      var media = image
        ? '<img src="' + esc(image) + '" alt="' + esc(name || item.store || '') + '" loading="lazy">'
        : '<div class="fz-tile-fallback">🛍️</div>';

      var h = '';
      h += '<a class="fz-tile" href="' + esc(url || '#') + '"' +
           (url ? ' target="_blank" rel="noopener sponsored"' : '') + '>';
      h += '<div class="fz-tile-media">' + media;
      if (isBest) h += '<span class="fz-pill fz-pill-best">' + esc(t('best_price')) + '</span>';
      if (flag)  h += '<span class="fz-pill fz-pill-origin"><span class="fz-pill-flag">' + esc(flag) + '</span></span>';
      h += '</div>';
      h += '<div class="fz-tile-body">';
      h += '<div class="fz-tile-store">' + esc(item.store || '') + '</div>';
      h += '<h3 class="fz-tile-name">' + esc(name) + '</h3>';
      h += '<div class="fz-tile-price">' + esc(item.price || t('fallback_price')) + '</div>';
      h += '</div></a>';
      return h;
    }

    function activateImages() {
      [].slice.call(section.querySelectorAll('.fz-tile-media img')).forEach(function(img) {
        function show(){ img.classList.add('is-loaded'); }
        function fail(){
          var box = img && img.parentNode;
          if (!box || box.getAttribute('data-fz-fallback') === '1') return;
          box.setAttribute('data-fz-fallback', '1');
          box.innerHTML = '<div class="fz-tile-fallback">🛍️</div>';
        }
        if (img.complete && img.naturalWidth > 0) show();
        else if (img.complete) fail();
        else {
          img.addEventListener('load', show, {once:true});
          img.addEventListener('error', fail, {once:true});
        }
      });
    }

    function updateHeading(n) {
      if (!resultsTitle) return;
      var head = lastQuery
        ? t('results_for') + ' · ' + lastQuery
        : t('results_photo');
      var countText = n ? ('<span>' + n + ' ' + esc(n === 1 ? t('count_one') : t('count_many')) + '</span>') : '';
      resultsTitle.innerHTML = esc(head) + countText;
    }

    function renderGrid() {
      var list = visibleItems();
      updateHeading(list.length);

      if (!list.length) {
        resultsBody.innerHTML = '<div class="fz-empty">' + esc(items.length ? t('no_filter') : t('no_results')) + '</div>';
        return;
      }

      var best = bestLocalKey();
      var grid = document.createElement('div');
      grid.className = 'fz-grid';

      list.forEach(function(item, i) {
        var k = keyOf(item);
        var holder = document.createElement('div');
        holder.innerHTML = tileHtml(item, k === best);
        var node = holder.firstElementChild;
        if (!node) return;
        node.classList.add('fz-fade');
        grid.appendChild(node);

        if (seenKeys[k]) {
          node.classList.add('is-in');
        } else {
          seenKeys[k] = true;
          setTimeout(function(){ node.classList.add('is-in'); }, Math.min(i, 8) * 55 + 20);
        }
      });

      resultsBody.innerHTML = '';
      resultsBody.appendChild(grid);
      activateImages();
    }

    function scheduleRender() {
      if (renderScheduled) return;
      renderScheduled = true;
      requestAnimationFrame(function() {
        renderScheduled = false;
        renderGrid();
      });
    }


    function renderMagicLoading(kind) {
      var message = kind === 'image' ? t('magic_image') : t('magic_text');

      var h = '<div class="fz-magic-caption"><span class="fz-magic-orb"></span><span>' + esc(message) + '</span></div>';
      h += '<div class="fz-magic-loading">';
      for (var i = 0; i < 6; i++) {
        h += '<div class="fz-magic-card">';
        h += '<div class="fz-magic-media"></div>';
        h += '<div class="fz-magic-lines">';
        h += '<div class="fz-magic-line"></div>';
        h += '<div class="fz-magic-line"></div>';
        h += '<div class="fz-magic-line"></div>';
        h += '</div></div>';
      }
      h += '</div>';
      resultsBody.innerHTML = h;
    }

    function resetResults(kind) {
      items = [];
      itemIndex = {};
      seenKeys = {};
      resultsShell.classList.add('is-visible');
      updateHeading(0);
      showingMagicLoading = true;
      renderMagicLoading(kind || 'text');
    }

    function showMessage(msg, isError) {
      showingMagicLoading = false;
      resultsShell.classList.add('is-visible');
      updateHeading(0);
      resultsBody.innerHTML = '<div class="fz-empty' + (isError ? ' fz-error' : '') + '">' + esc(msg) + '</div>';
    }

    function upsert(item) {
      if (!item || !plausible(item)) return;
      if (showingMagicLoading) {
        showingMagicLoading = false;
        resultsBody.innerHTML = '';
      }
      var m = String(item.market || '');
      if (m !== 'local' && m !== 'us' && m !== 'china') return;
      var k = keyOf(item);
      if (!k) return;
      if (itemIndex[k] != null) {
        items[itemIndex[k]] = item;
      } else {
        // True FIFO: whichever merchant result reaches the browser first keeps its position.
        // Local remains searchable/filterable, but it no longer jumps ahead of faster stores.
        items.push(item);
        itemIndex[k] = items.length - 1;
      }
      scheduleRender();
    }

    function validCountryCode(value) {
      return /^[A-Za-z]{2}$/.test(String(value || '').trim());
    }

    function updateLocalFilterLabel() {
      var btn = section.querySelector('[data-local-label]');
      if (!btn) return;
      btn.textContent = marketCountryName || (lang() === 'ar' ? 'محلي' : 'Local');
    }

    function setDetectedMarketCountry(value, name) {
      var cc = String(value || '').trim().toUpperCase();
      if (!validCountryCode(cc)) return false;
      var changed = marketCountry !== cc;
      marketCountry = cc;
      if (name) marketCountryName = String(name).trim();
      marketCountryReady = true;
      updateLocalFilterLabel();
      updateLanguageToggle(changed);
      try {
        localStorage.setItem(geoStorageKey, cc);
        localStorage.setItem(geoNameStorageKey, marketCountryName || '');
        localStorage.setItem(geoStorageTsKey, String(Date.now()));
      } catch(e) {}
      return true;
    }

    async function detectMarketCountry() {
      try {
        var cached = localStorage.getItem(geoStorageKey);
        var cachedName = localStorage.getItem(geoNameStorageKey) || '';
        var cachedTs = Number(localStorage.getItem(geoStorageTsKey) || 0);
        if (validCountryCode(cached) && cachedTs && (Date.now() - cachedTs) < 24 * 60 * 60 * 1000) {
          setDetectedMarketCountry(cached, cachedName);
        }
      } catch(e) {}

      if (!apiBase) { marketCountryReady = true; return marketCountry; }
      try {
        var controller = window.AbortController ? new AbortController() : null;
        var timer = controller ? setTimeout(function(){ controller.abort(); }, 2600) : null;
        var res = await fetch(apiBase + '/api/geo', {
          method:'GET', headers:{'Accept':'application/json'}, cache:'no-store',
          signal: controller ? controller.signal : undefined
        });
        if (timer) clearTimeout(timer);
        if (res.ok) {
          var data = await res.json().catch(function(){ return {}; });
          if (data && data.ok && validCountryCode(data.country || data.country_code)) {
            setDetectedMarketCountry(data.country || data.country_code, data.country_name || '');
          }
        }
      } catch(e) {}
      marketCountryReady = true;
      return marketCountry;
    }

    var marketCountryPromise = detectMarketCountry();

    async function currentMarketCountry() {
      if (!marketCountryReady) {
        try {
          await Promise.race([
            marketCountryPromise,
            new Promise(function(resolve){ setTimeout(resolve, 650); })
          ]);
        } catch(e) {}
      }
      return marketCountry || shopifyCountry || 'KW';
    }

    async function apiStream(path, payload, onEvent) {
      if (!apiBase) throw new Error('API URL missing');
      var res = await fetch(apiBase + path, {
        method:'POST',
        headers:{'Content-Type':'application/json','Accept':'application/x-ndjson'},
        body:JSON.stringify(payload)
      });
      if (!res.ok) throw new Error(await res.text().catch(function(){ return 'HTTP ' + res.status; }));
      if (!res.body || !res.body.getReader) throw new Error('stream_unsupported');
      var reader = res.body.getReader(), dec = new TextDecoder(), buf = '';
      while (true) {
        var part = await reader.read();
        if (part.done) break;
        buf += dec.decode(part.value, {stream:true});
        var lines = buf.split('\n');
        buf = lines.pop() || '';
        for (var i = 0; i < lines.length; i++) {
          var line = lines[i].trim();
          if (!line) continue;
          try { await onEvent(JSON.parse(line)); } catch (e) {}
        }
      }
      if (buf.trim()) { try { await onEvent(JSON.parse(buf.trim())); } catch (e) {} }
    }

    async function apiPost(path, payload) {
      if (!apiBase) throw new Error('API URL missing');
      var res = await fetch(apiBase + path, {
        method:'POST',
        headers:{'Content-Type':'application/json','Accept':'application/json'},
        body:JSON.stringify(payload)
      });
      var data = await res.json().catch(function(){ return {}; });
      if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
      return data;
    }

    function renderRecommendations(data) {
      showingMagicLoading = false;
      var options = Array.isArray(data.options) ? data.options : [];
      if (!options.length) return showMessage(t('no_results'), false);
      var h = data.comparison ? '<div style="margin-bottom:14px;font-weight:600;color:#16211f;">' + esc(data.comparison) + '</div>' : '';
      options.forEach(function(o){ h += '<button class="fz-chip" type="button" data-option="' + esc(o) + '">' + esc(o) + '</button>'; });
      resultsShell.classList.add('is-visible');
      updateHeading(0);
      resultsBody.innerHTML = '<div class="fz-empty">' + h + '</div>';
      [].slice.call(resultsBody.querySelectorAll('[data-option]')).forEach(function(b){
        b.addEventListener('click', function(){
          runTextSearch(b.getAttribute('data-option'), {
            selectedOption: b.getAttribute('data-option'),
            originalQuery: data.query || (queryInput && queryInput.value) || ''
          });
        });
      });
    }

    function ingestBatch(data) {
      showingMagicLoading = false;
      if (data && data.type === 'recommendations') return renderRecommendations(data);
      var list = Array.isArray(data && data.results) ? data.results : [];
      list.forEach(upsert);
      if (!items.length) showMessage(t('no_results'), false);
    }

    async function runTextSearch(value, opts) {
      var activeCountry = await currentMarketCountry();
      var q = (value || (queryInput && queryInput.value) || '').trim();
      if (!q) { if (queryInput) queryInput.focus(); return; }
      if (queryInput) queryInput.value = q;
      if (waLink) waLink.href = waUrl();
      lastQuery = q;
      var token = ++renderToken;
      setBusy(true, t('searching'));
      resetResults('text');

      var payload = { query:q, country:activeCountry, lang:lang() };
      if (opts && opts.selectedOption) {
        payload.selected_option = opts.selectedOption;
        payload.original_query = opts.originalQuery || q;
        payload.force_specific = true;
      }

      try {
        await apiStream('/api/search/stream', payload, async function(ev) {
          if (token !== renderToken || !ev) return;
          if (ev.event === 'result' || ev.event === 'upsert') upsert(ev.item || {});
          else if (ev.event === 'recommendations') renderRecommendations(ev.data || {});
          else if (ev.event === 'done') setBusy(false);
          else if (ev.event === 'error') throw new Error(ev.error || 'search_failed');
        });
        if (token === renderToken) {
          setBusy(false);
          if (!items.length && !resultsBody.querySelector('.fz-empty')) showMessage(t('no_results'), false);
        }
      } catch (err) {
        if (token !== renderToken) return;
        try {
          var data = await apiPost('/api/search', payload);
          if (token !== renderToken) return;
          setBusy(false);
          ingestBatch(data);
        } catch (e2) {
          setBusy(false);
          showMessage(t('error_text'), true);
        }
      }
    }

    function readFile(file) {
      return new Promise(function(resolve, reject) {
        var r = new FileReader();
        r.onload = function(){
          var s = String(r.result), c = s.indexOf(',');
          resolve(c >= 0 ? s.slice(c + 1) : s);
        };
        r.onerror = reject;
        r.readAsDataURL(file);
      });
    }

    async function runImageSearch(file) {
      if (!file) return;
      var activeCountry = await currentMarketCountry();
      if (file.size > 6 * 1024 * 1024) {
        return showMessage(lang() === 'ar' ? 'الصورة كبيرة. اختر صورة أقل من 6 ميغابايت.' : 'That image is over 6 MB. Choose a smaller one.', true);
      }
      var token = ++renderToken;
      lastQuery = '';
      setBusy(true, t('searching_image'));
      resetResults('image');

      try {
        var b64 = await readFile(file);
        var payload = {
          image_base64: b64,
          mime_type: file.type || 'image/jpeg',
          caption: (queryInput && queryInput.value || '').trim(),
          country: activeCountry,
          lang: lang()
        };
        try {
          await apiStream('/api/search/image/stream', payload, async function(ev) {
            if (token !== renderToken || !ev) return;
            if (ev.event === 'result' || ev.event === 'upsert') upsert(ev.item || {});
            else if (ev.event === 'done') {
             setBusy(false);
             if (!items.length && showingMagicLoading) {
               showingMagicLoading = false;
               showMessage(t('no_results'), false);
             }
           }
            else if (ev.event === 'error') throw new Error(ev.error || 'image_search_failed');
          });
          if (token === renderToken) {
            setBusy(false);
            if (!items.length && !resultsBody.querySelector('.fz-empty')) showMessage(t('no_results'), false);
          }
        } catch (streamErr) {
          if (token !== renderToken) return;
          var data = await apiPost('/api/search/image', payload);
          if (token !== renderToken) return;
          setBusy(false);
          ingestBatch(data);
        }
      } catch (err) {
        if (token !== renderToken) return;
        setBusy(false);
        showMessage(t('error_image'), true);
      } finally {
        if (photoInput) photoInput.value = '';
      }
    }

    if (waLink) waLink.href = waUrl();
    searchButtons.forEach(function(b){ b.addEventListener('click', function(){ runTextSearch(); }); });
    if (queryInput) {
      queryInput.addEventListener('input', function(){ if (waLink) waLink.href = waUrl(); });
      queryInput.addEventListener('keydown', function(e){
        if (e.key === 'Enter') { e.preventDefault(); runTextSearch(); }
      });
    }
    if (photoButton && photoInput) {
      photoButton.addEventListener('click', function(){ photoInput.click(); });
      photoInput.addEventListener('change', function(){
        if (photoInput.files && photoInput.files[0]) runImageSearch(photoInput.files[0]);
      });
    }
    if (filterSeg) {
      filterSeg.addEventListener('click', function(e) {
        var b = e.target.closest('[data-filter]');
        if (!b) return;
        activeFilter = b.getAttribute('data-filter');
        [].slice.call(filterSeg.querySelectorAll('button')).forEach(function(x){
          x.classList.toggle('is-active', x === b);
        });
        renderGrid();
      });
    }
    if (sortSeg) {
      sortSeg.addEventListener('click', function(e) {
        var b = e.target.closest('[data-sort]');
        if (!b) return;
        activeSort = b.getAttribute('data-sort');
        [].slice.call(sortSeg.querySelectorAll('button')).forEach(function(x){
          x.classList.toggle('is-active', x === b);
        });
        renderGrid();
      });
    }
    langButtons.forEach(function(b){
      b.addEventListener('click', function(){ applyLang(b.getAttribute('data-lang-btn')); });
    });

    // Initial language follows the detected/local country. The async GeoIP call
    // will refresh this again if Shopify's initial country differs from the visitor IP.
    localLangCode = localLanguageForCountry(marketCountry);
    var saved = '';
    try { saved = localStorage.getItem(storageKey) || ''; } catch (e) {}
    activeLang = (saved === 'en' || saved === localLangCode) ? saved : localLangCode;
    updateLanguageToggle(false);
  })();
</script>

{% schema %}
{
  "name": "Findzia Home V26",
  "tag": "section",
  "class": "section-findzia-home",
  "settings": [
    { "type": "image_picker", "id": "logo", "label": "Findzia logo" },
    {
      "type": "text",
      "id": "api_base_url",
      "label": "Findzia API base URL",
      "default": "https://coop-bot-g-production.up.railway.app"
    },
    {
      "type": "text",
      "id": "whatsapp_number",
      "label": "WhatsApp number",
      "info": "Country code only, no + sign",
      "default": "96500000000"
    }
  ],
  "presets": [{ "name": "Findzia Home V26" }]
}
{% endschema %}
