# Security notes

Meant for a trusted home network. Do not publish the analyzer through a reverse proxy or the internet.

## What protects what
- **Login:** one admin from the environment, argon2id, signed session cookie (HttpOnly, SameSite=Strict), CSRF token on every state-changing form, rate limit per address. Sign-out revokes the session cookie.
- **API token:** read-only access to recordings (plus the rate-limited knowledge update). Guessing is throttled like password guessing. Use 16+ random characters; `SESSION_SECRET` needs 32+ (below 16 the app refuses to start).
- **Configuration, deletion, backup, restore, device keys** need a real login session, never only the API token.
- **Nothing is sent to appliances.** The collector only connects and subscribes to the ESPHome log stream.
- **Browser:** strict CSP (no inline scripts), no `innerHTML` in the scripts, `frame-ancestors 'none'`, `no-store`, `nosniff`, no referrer.
- **Free text** (type, manufacturer, model, notes) is length-limited and escaped on output.
- **Restore** accepts only plain SQLite data (no triggers, views, virtual tables), checks integrity and keeps a safety copy during the restore.
- **Knowledge updates** fetch only data files named in a manifest, over https (redirects to http are refused), verify SHA-256, cap sizes and YAML aliases, validate with the normal spec/catalogue checks and roll back on any problem.
- **Container:** runs as a non-root user; secrets only through environment variables.

## HTTPS (optional)
The LAN default is plain HTTP; the session cookie is then not `Secure`. `DBA_TLS=1` serves HTTPS: a local CA and a server certificate
(EC P-256) are created in the data volume (`tls/`, private keys mode 600; only `/tls/ca.crt` is public), cookies become `Secure`.
The MCP extension verifies the certificate against the system roots plus the optional CA file and never disables verification.
Use HTTP only on a trusted network segment; HSTS is deliberately not sent.

## Signed knowledge updates
Knowledge updates are verified by SHA-256 over HTTPS and, once the project ships a public key (`knowledge-pubkey.txt`), by an
Ed25519 signature over the manifest (`knowledge-manifest.json.sig`): without a valid signature nothing is downloaded or activated.
Maintainer: `dba knowledge-keygen <private-key-file>` once (keep the key out of the repository), then after every knowledge change
`dba build-knowledge --sign <private-key-file>`; the test suite fails when the committed signature is stale.

## Things to know
- The ESPHome API keys are stored in clear text in the SQLite file and therefore also in every backup. Keep backups private.
- The API token lives in the Claude Desktop extension settings on your computer.
- Knowledge updates trust the project repository (specs, catalogue and the example firmware files you may flash). Switch the daily check off on the Device knowledge page if you do not want that; the bundled files stay available.
- Plain HTTP on the LAN is the default. Behind HTTPS set `COOKIE_SECURE=1`.
- Failed-login counters and revoked sessions are kept in memory and reset on restart.

Report problems privately through GitHub security advisories of this repository.
