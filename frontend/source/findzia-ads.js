/* Google Ads: count merchant-link activations, never page loads as conversions. */
(function () {
  'use strict';
  if (window.FindziaAdsInstalled) return;
  window.FindziaAdsInstalled = true;
  var internal=false;
  try {
    var test=new URL(window.location.href).searchParams.get('fz_test');
    internal=test==='1'||(test!=='0'&&localStorage.getItem('findzia-internal-traffic')==='1');
    if(test==='1'||test==='0')localStorage.setItem('findzia-internal-traffic',test);
  } catch (_) {}
  window.FindziaTraffic={internal:internal};
  if(internal)return; // Owner tests never send Ads conversions or GA events.
  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
  window.gtag('js', new Date());
  window.gtag('config', 'AW-18499186413');
  var script = document.createElement('script');
  script.async = true;
  script.src = 'https://www.googletagmanager.com/gtag/js?id=AW-18499186413';
  document.head.appendChild(script);

  function track(event) {
    if (event.defaultPrevented || event.isTrusted === false) return;
    if (event.type === 'click' && event.button !== 0) return;
    if (event.type === 'auxclick' && event.button !== 1) return;
    var anchor = event.target.closest && event.target.closest('a.fz-tile, a.fz-quick-card, a.fz-saved-link, a.fz-insights-cta');
    if (!anchor) return;
    try {
      var url = new URL(anchor.href, window.location.href);
      if (!/^https?:$/.test(url.protocol) || url.hostname === 'findzia.com' || url.hostname.endsWith('.findzia.com') || url.origin === window.location.origin) return;
      // Preserve native target=_blank, modifier keys and navigation even if Ads is blocked.
      window.gtag('event', 'conversion', {
        send_to: 'AW-18499186413/Z9ulCObypZQdEO3djPVE',
        value: 1.0,
        currency: 'USD'
      });
    } catch (_) { /* Tracking must never interrupt shopping. */ }
  }
  document.addEventListener('click', track);
  document.addEventListener('auxclick', track);
})();
