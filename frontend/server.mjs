// Dedicated static storefront. Never install this server in the existing API service.
import http from 'node:http';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const base = resolve(dirname(fileURLToPath(import.meta.url)), 'public');
const manifest = JSON.parse(readFileSync(resolve(base, 'release.json'), 'utf8'));
const association = '/.well-known/apple-developer-merchantid-domain-association';
const routes = new Map();
const csp = "default-src 'self'; script-src 'self' 'unsafe-inline' https://*.myfatoorah.com https://cdn.paddle.com https://www.googletagmanager.com https://www.googleadservices.com https://www.google.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; connect-src 'self' https://api.findzia.com https://*.myfatoorah.com https://*.paddle.com https://www.googletagmanager.com https://www.googleadservices.com https://googleads.g.doubleclick.net https://pagead2.googlesyndication.com https://www.google.com https://www.google.com.kw https://www.google.com.sa https://ad.doubleclick.net; img-src 'self' https: data: blob:; frame-src https://*.myfatoorah.com https://*.paddle.com https://www.googletagmanager.com; media-src 'self' blob:; worker-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self' https://*.myfatoorah.com https://*.paddle.com";
const common = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'X-Frame-Options': 'DENY',
  // The PSP SDK uses a payment iframe. Do not restrict payment to self.
  'Permissions-Policy': 'payment=*, camera=(self), microphone=(self)',
  'Content-Security-Policy': csp,
};
const types = {html:'text/html; charset=utf-8', js:'text/javascript; charset=utf-8', css:'text/css; charset=utf-8', json:'application/json; charset=utf-8', txt:'text/plain; charset=utf-8', xml:'application/xml; charset=utf-8', svg:'image/svg+xml'};
for (const [url, entry] of Object.entries(manifest.routes)) {
  // Load only build-manifest entries, never a path supplied by an HTTP client.
  const path = resolve(base, entry.file);
  if (!path.startsWith(base + '/')) throw Error('Invalid build manifest');
  const body = readFileSync(path), hash = createHash('sha256').update(body).digest('hex');
  if (hash !== entry.sha256) throw Error('Build integrity mismatch: ' + entry.file);
  routes.set(url, {body, hash, type: types[entry.type], immutable: entry.immutable === true});
}
if (routes.get(association)?.hash !== manifest.apple_pay_file_sha256) throw Error('Verification file mismatch');

const applePayFiles = new Map();
for (const provider of ['paddle','myfatoorah']) {
  const entry = manifest.apple_pay_files?.[provider];
  if (!entry || entry.file !== 'apple-pay/'+provider) throw Error('Missing Apple Pay file: '+provider);
  const body = readFileSync(resolve(base,entry.file));
  const hash = createHash('sha256').update(body).digest('hex');
  if (hash !== entry.sha256) throw Error('Apple Pay file integrity mismatch: '+provider);
  applePayFiles.set(provider,{body,hash,type:types.txt,immutable:false});
}

export function createServer(env=process.env) {
  const provider = String(env.FINDZIA_PAYMENT_PROVIDER ?? 'paddle').trim().toLowerCase();
  if (!applePayFiles.has(provider)) throw Error('FINDZIA_PAYMENT_PROVIDER must be paddle or myfatoorah');
  const selectedFile = applePayFiles.get(provider);
  const health = Buffer.from(JSON.stringify({...JSON.parse(routes.get('/healthz').body),
    payment_provider:provider,apple_pay_file_sha256:selectedFile.hash,apple_pay_switch:'railway-variable-v1'}));
  const healthEntry = {body:health,hash:createHash('sha256').update(health).digest('hex'),type:types.json,immutable:false};
  console.log(`FINDZIA_APPLE_PAY_FILE provider=${provider} sha256=${selectedFile.hash}`);
  return http.createServer({maxHeaderSize: 16384, requestTimeout: 15000, headersTimeout: 10000}, (req, res) => {
    if (!['GET', 'HEAD'].includes(req.method)) {
      res.writeHead(405, {...common, Allow:'GET, HEAD', 'Cache-Control':'no-store'}); res.end(); return;
    }
    // No canonical-domain, slash or HTTPS redirects here: the provider must
    // receive the file itself on each HTTPS host, not a redirected document.
    const path = (req.url || '/').split('?')[0];
    const entry = path===association ? selectedFile : path==='/healthz' ? healthEntry : routes.get(path);
    if (!entry) {
      const page = routes.get('/404.html');
      res.writeHead(404, {...common, 'Content-Type':types.html, 'Cache-Control':'no-store', 'Content-Length':page.body.length});
      res.end(req.method === 'HEAD' ? undefined : page.body); return;
    }
    const headers = {...common, 'Content-Type':entry.type, 'Content-Length':entry.body.length,
      'Cache-Control': path === association ? 'no-store' : entry.immutable ? 'public, max-age=31536000, immutable' : 'no-cache',
      ETag:'"'+entry.hash+'"', 'X-Findzia-Build':manifest.version};
    if (!['findzia.com','www.findzia.com'].includes((req.headers.host || '').toLowerCase().split(':')[0])) {
      headers['X-Robots-Tag'] = 'noindex, nofollow';
    }
    // Always return the association bytes, even if a browser sends an old ETag.
    if (path !== association && req.headers['if-none-match'] === headers.ETag) {
      delete headers['Content-Length']; res.writeHead(304, headers); res.end(); return;
    }
    res.writeHead(200, headers); res.end(req.method === 'HEAD' ? undefined : entry.body);
  });
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.PORT || 8080), server = createServer();
  server.listen(port, '0.0.0.0', () => console.log(`FINDZIA_FRONTEND build=${manifest.version} port=${port}`));
  for (const signal of ['SIGTERM','SIGINT']) process.on(signal, () => {
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(1), 8000).unref();
  });
}
