"""Single admin account from environment variables: argon2id, signed cookie sessions, CSRF token, login rate limit."""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import Settings

log = logging.getLogger("dba.auth")
COOKIE = "dba_session"
CSRF_COOKIE = "dba_csrf"


class Auth:
    def __init__(self, s: Settings):
        if not s.admin_email or not (s.admin_password or s.admin_password_hash):
            raise RuntimeError("ADMIN_EMAIL and ADMIN_PASSWORD (or ADMIN_PASSWORD_HASH) must be set")
        if s.session_secret and len(s.session_secret) < 16:
            raise RuntimeError("SESSION_SECRET is too short: use 32+ random characters (anyone could forge session cookies otherwise)")
        if s.session_secret and len(s.session_secret) < 32:
            log.warning("SESSION_SECRET has fewer than 32 characters; use 32+ random characters")
        if s.api_token and len(s.api_token) < 16:
            log.warning("API_TOKEN has fewer than 16 characters; use a long random token (it gives read access to all recordings)")
        self.email = s.admin_email
        self.ph = PasswordHasher()
        self.hash = self._pick_hash(s)
        self.ser = URLSafeTimedSerializer(s.session_secret or secrets.token_urlsafe(32), salt="dba-session")
        self.max_age = s.session_hours * 3600
        self.token = s.api_token
        self._fails: dict[str, deque] = defaultdict(deque)
        self._revoked: dict[str, float] = {}                 # digests of signed-out session cookies, kept until they would expire anyway
        self.max_fails, self.window = 5, 300.0
        self._dummy = self.ph.hash("dummy-password-for-timing")

    def _pick_hash(self, s: Settings) -> str:
        """Use ADMIN_PASSWORD_HASH if it is a valid argon2 hash, else fall back to ADMIN_PASSWORD (with a warning)."""
        h = s.admin_password_hash.strip()
        if h:
            try:
                self.ph.check_needs_rehash(h)
                return h
            except InvalidHashError:
                log.warning("ADMIN_PASSWORD_HASH is not a valid argon2 hash (a '$' lost to variable substitution?)%s",
                            "; using ADMIN_PASSWORD instead" if s.admin_password else "")
                if not s.admin_password:
                    raise RuntimeError("ADMIN_PASSWORD_HASH is not a valid argon2 hash and ADMIN_PASSWORD is empty") from None
        return self.ph.hash(s.admin_password)

    def locked(self, ip: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        q = self._fails[ip]
        while q and now - q[0] > self.window:
            q.popleft()
        return len(q) >= self.max_fails

    def check_login(self, ip: str, email: str, password: str) -> bool:
        if self.locked(ip):
            return False
        ok_mail = hmac.compare_digest(email.strip().lower().encode(), self.email.encode())
        try:
            self.ph.verify(self.hash if ok_mail else self._dummy, password)   # same work for wrong e-mail
            ok = ok_mail
        except (VerifyMismatchError, InvalidHashError):
            ok = False
        if not ok:
            log.warning("login failed: e-mail %s, password %s", "matches" if ok_mail else "does not match",
                        "wrong" if ok_mail else "not checked against this account")
            self._fails[ip].append(time.time())
        else:
            self._fails.pop(ip, None)
        return ok

    def revoke(self, cookie: str | None) -> None:
        """Sign-out really ends the session: a copied cookie stops working too (kept in memory until its normal expiry)."""
        now = time.time()
        for d, ts in list(self._revoked.items()):
            if now - ts > self.max_age:
                del self._revoked[d]
        if cookie:
            self._revoked[hashlib.sha256(cookie.encode()).hexdigest()] = now

    def token_attempt(self, ip: str, ok: bool) -> bool:
        """Throttle guessing of the API token like password guessing. Returns False while this address is locked out."""
        key = "t:" + ip
        if self.locked(key):
            return False
        if not ok:
            self._fails[key].append(time.time())
        return True

    def make_session(self) -> str:
        return self.ser.dumps({"u": self.email})

    def valid_session(self, cookie: str | None) -> bool:
        if not cookie or hashlib.sha256(cookie.encode()).hexdigest() in self._revoked:
            return False
        try:
            return self.ser.loads(cookie, max_age=self.max_age).get("u") == self.email
        except BadSignature:
            return False

    def csrf_for(self, session_cookie: str) -> str:
        """CSRF token for state-changing requests of a logged-in session (logout), bound to the session cookie."""
        return hmac.new(self.ser.secret_keys[-1], b"csrf:" + session_cookie.encode(), "sha256").hexdigest()

    def valid_token(self, header: str | None) -> bool:
        if not self.token or not header or not header.lower().startswith("bearer "):
            return False
        return hmac.compare_digest(header[7:].strip().encode(), self.token.encode())
