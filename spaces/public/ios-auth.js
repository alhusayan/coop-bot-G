(() => {
  'use strict';
  const params = new URLSearchParams(location.hash.slice(1));
  const code = params.get('findzia-login'), flow = params.get('flow');
  const result = new URLSearchParams();
  if (/^[A-Za-z0-9_-]{20,200}$/.test(code || '') && /^[A-Za-z0-9_-]{24,100}$/.test(flow || '')) {
    result.set('findzia-login', code); result.set('flow', flow);
  } else if (params.get('findzia-auth-error')) result.set('findzia-auth-error', 'sign_in_failed');
  else { document.getElementById('status').textContent = 'Please start sign-in from the Findzia app.'; return; }
  history.replaceState(null, '', location.pathname);
  const target = 'findzia-ios://auth/callback#' + result.toString();
  const link = document.getElementById('continue'); link.href = target; link.hidden = false;
  location.replace(target);
})();
