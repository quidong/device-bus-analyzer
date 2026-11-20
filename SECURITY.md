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

## Things to know
- The ESPHome API keys are stored in clear text in the SQLite file and therefore also in every backup. Keep backups private.
- The API token lives in the Claude Desktop extension settings on your computer.
- Knowledge updates trust the project repository (specs, catalogue and the example firmware files you may flash). Switch the daily check off on the Device knowledge page if you do not want that; the bundled files stay available.
- Plain HTTP on the LAN is the default. Behind HTTPS set `COOKIE_SECURE=1`.
- Failed-login counters and revoked sessions are kept in memory and reset on restart.

Report problems privately through GitHub security advisories of this repository.
