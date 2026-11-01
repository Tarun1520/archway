# Security

What protects Archway, and the checklist for deploying it. Every item below is in the code and, where it can be,
covered by a test (`backend/tests/test_security.py`, `test_auth.py`, `test_no_secrets.py`).

## Secrets (model, GitHub, voice and decision keys)

- Keys live only in `backend/.env` on your machine, and in the backend host's secret settings once deployed. They are
  read by the backend and never sent to the browser: `/api/config` returns an explicit list of public fields, and a
  test scans every API answer, the frontend source and the built bundle for real key values.
- Every message that leaves the backend (HTTP error answers, the live run events) passes through a scrubber
  (`app/security/scrub.py`) that removes the known key values and anything shaped like a key or token, because
  outside services sometimes echo part of a key in their error text. Log lines are scrubbed the same way.
- `.gitignore` and `.vercelignore` keep `.env` files, databases and the whole backend out of git and out of Vercel.
- The production build ships no source maps.

## Accounts and sessions

- Passwords are stored only as salted scrypt hashes. A password may not be the email or a very common one.
- Signing in creates a new random session token (never reuses one), kept in a cookie that page scripts cannot read
  (`HttpOnly`), that other sites cannot send (`SameSite=Lax`), and on HTTPS that is `Secure` and named with the
  `__Host-` prefix. The database stores only the token's fingerprint. Signing out ends the session on the server.
- 5 wrong passwords per email (or 20 per address) in 15 minutes are refused for a while; at most 5 new accounts per
  address per hour. Wrong email and wrong password get the same answer in the same time.
- Each account sees only its own projects and runs; anything else answers 404. The admin sees usage counts, never
  other people's projects. An admin cannot block or demote themselves or the last admin; blocking signs a person out
  everywhere.

## Requests and pages

- Requests that change data, and the voice WebSocket, are refused unless they come from Archway's own site
  (`app/security/guard.py`): no cross-site request forgery, no cross-site WebSocket hijacking.
- Every API answer: `nosniff`, no framing (`X-Frame-Options: DENY`, `frame-ancestors 'none'`), `no-referrer`,
  `no-store`, and on HTTPS, HSTS. The API docs are off on HTTPS.
- The site itself (`frontend/vercel.json`): a strict Content-Security-Policy (scripts only from Archway itself, no
  framing, forms only to Archway), HSTS, `nosniff`, `no-referrer`. Tried locally on the built app with `vite preview`
  (same headers): no violations.
- Redirects only ever go to fixed addresses inside the app (`#/login`, `#/studio`); nothing takes a destination from
  the address bar, so the sign-in page cannot be used to send people to a look-alike site.
- Links built from research data are only kept if they are `https://`; diagrams are drawn by Mermaid in strict mode
  from a source the backend already checked; all other text is rendered as text, never as HTML.
- SQL always uses placeholders. Web pages are fetched through the safe fetcher (no private addresses, size and time
  limits). Text from READMEs and web pages is data for the agents, never instructions.

## Deploying: checklist

1. Backend host: set the keys as secret environment variables there (never upload `.env`), plus
   `COOKIE_SECURE=true`, `ALLOWED_ORIGINS=https://<your-vercel-domain>`, `ADMIN_EMAIL=<you>`, `AUTH_ENABLED=true`.
2. Run the backend behind the host's HTTPS, with `--proxy-headers` and the host's proxy in `--forwarded-allow-ips`,
   so the sign-in limits see each visitor's real address.
3. Vercel: project root `frontend/`; add the `/api` rewrite to the backend host in `vercel.json` (the cookie then stays
   on your own domain).
4. After deploying, check: the headers (securityheaders.com), that `/docs` answers 404, that signing up and in works,
   and that a second account cannot see the first one's project.
5. If a key was ever pasted anywhere outside `.env` (chat, a screenshot, a commit), rotate it at the provider.

## Known limits

- There is no email verification or password reset yet: an admin can block an account, but a forgotten password
  needs `backend/scripts/make_admin.py` or a new account. Add both before opening sign-up widely.
- The sign-in limits are kept in memory: they reset on restart and assume one backend server.
- Voice (Archy) and brief suggestions are not counted in token quotas yet.
- `backend/.env` sits in an iCloud Drive folder, so it is synced to your iCloud account. Keep iCloud protected with
  two-factor sign-in, or move the project out of iCloud.
