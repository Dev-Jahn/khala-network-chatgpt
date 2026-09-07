import base64
from contextlib import contextmanager
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import time


class Store:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if directory.stat().st_mode & 0o077:
            raise ValueError("state_dir must have mode 0700")
        self.path = directory / "bridge.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS mailboxes (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, created INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS bindings (
                    owner TEXT NOT NULL, conversation TEXT NOT NULL, mailbox TEXT NOT NULL,
                    PRIMARY KEY(owner, conversation));
                CREATE TABLE IF NOT EXISTS secrets (name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sends (
                    mailbox TEXT NOT NULL, request TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    message_id TEXT, PRIMARY KEY(mailbox, request));
            """)
            db.execute("INSERT OR IGNORE INTO secrets VALUES ('receipt-key', ?)", (secrets.token_hex(32),))
            self.key = bytes.fromhex(db.execute("SELECT value FROM secrets WHERE name='receipt-key'").fetchone()[0])
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def owned(self, owner: str, mailbox: str):
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM mailboxes WHERE id=? AND owner=?", (mailbox, owner)).fetchone():
                raise ValueError("Mailbox not found or not owned by this authenticated user")

    def open(self, owner: str, conversation: str, resume: str | None) -> str:
        if not conversation or len(conversation) > 512:
            raise ValueError("A conversation key of 1..512 characters is required")
        conversation = hashlib.sha256(conversation.encode()).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if resume:
                if not db.execute("SELECT 1 FROM mailboxes WHERE id=? AND owner=?", (resume, owner)).fetchone():
                    raise ValueError("Cannot resume another user's mailbox")
                mailbox = resume
            else:
                found = db.execute("SELECT mailbox FROM bindings WHERE owner=? AND conversation=?",
                                   (owner, conversation)).fetchone()
                if found:
                    return found[0]
                mailbox = "cg-" + secrets.token_hex(12)
                db.execute("INSERT INTO mailboxes VALUES (?, ?, ?)", (mailbox, owner, int(time.time())))
            db.execute("INSERT OR REPLACE INTO bindings VALUES (?, ?, ?)", (owner, conversation, mailbox))
            return mailbox

    def sign(self, claims: dict) -> str:
        payload = base64.urlsafe_b64encode(json.dumps({**claims, "exp": int(time.time()) + 86400},
                                                     separators=(",", ":")).encode()).decode().rstrip("=")
        signature = hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()
        return payload + "." + signature

    def verify(self, token: str, owner: str, mailbox: str, kind: str) -> dict:
        try:
            if len(token) > 4096:
                raise ValueError()
            payload, signature = token.rsplit(".", 1)
            expected = hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError()
            claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
            if (claims["owner"], claims["mailbox"], claims["kind"]) != (owner, mailbox, kind):
                raise ValueError()
            if claims["exp"] <= time.time():
                raise ValueError()
            return claims
        except (ValueError, KeyError, TypeError):
            raise ValueError("Invalid, expired, or wrong-owner receipt/cursor") from None

    def prepare_send(self, mailbox: str, request: str, fingerprint: str):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO sends VALUES (?, ?, ?, NULL)", (mailbox, request, fingerprint))
            old = db.execute("SELECT fingerprint FROM sends WHERE mailbox=? AND request=?", (mailbox, request)).fetchone()
            if old[0] != fingerprint:
                raise ValueError("request_id was already used with different message content")

    def sent(self, mailbox: str, request: str, message_id: str):
        with self.connect() as db:
            db.execute("UPDATE sends SET message_id=? WHERE mailbox=? AND request=?", (message_id, mailbox, request))

    def send_record(self, mailbox: str, request: str):
        with self.connect() as db:
            return db.execute("SELECT message_id FROM sends WHERE mailbox=? AND request=?", (mailbox, request)).fetchone()
