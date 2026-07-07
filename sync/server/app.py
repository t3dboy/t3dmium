"""T3dmium sync server — a dumb, zero-knowledge encrypted blob store.

Pure Python 3.9 standard library: http.server + sqlite3. No third-party
dependencies. The server NEVER sees plaintext, encryption keys, or any secret
that can decrypt data; it stores only opaque ciphertext and a HASH of the
group auth token.

Self-hosting: binds to 127.0.0.1 by default. Speaks plain HTTP — put your own
TLS-terminating reverse proxy in front for anything beyond localhost. See
../README.md and ../PROTOCOL.md.

Author: Ted Roubour
License: see ../../LICENSE

Run:
    python3 app.py --host 127.0.0.1 --port 8787 --db data.db
"""

import argparse
import hashlib
import hmac
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sqlite3
from urllib.parse import urlparse, parse_qs

MAX_BODY = 8 * 1024 * 1024          # 8 MiB cap per request
MAX_RECORDS_PER_BATCH = 1000


# --- Storage ----------------------------------------------------------------

class Store:
    """SQLite-backed store, thread-safe via a lock. Suitable for a self-hosted,
    low-concurrency personal sync server."""

    def __init__(self, db_path: str = "data.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        if db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS groups (
                    group_id     TEXT PRIMARY KEY,
                    auth_hash    TEXT NOT NULL,
                    pairing_salt TEXT,
                    created_at   REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS records (
                    group_id   TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    id         TEXT NOT NULL,
                    nonce      TEXT NOT NULL,
                    ciphertext TEXT NOT NULL,
                    version    INTEGER NOT NULL,
                    tombstone  INTEGER NOT NULL DEFAULT 0,
                    alg        TEXT NOT NULL,
                    seq        INTEGER NOT NULL,
                    PRIMARY KEY (group_id, collection, id)
                );
                CREATE INDEX IF NOT EXISTS idx_records_seq
                    ON records (group_id, seq);
                CREATE TABLE IF NOT EXISTS seq_counter (
                    group_id TEXT PRIMARY KEY,
                    seq      INTEGER NOT NULL
                );
                """
            )
            self._conn.commit()

    # -- groups --
    def create_group(self, group_id: str, auth_hash: str, pairing_salt):
        with self._lock:
            row = self._conn.execute(
                "SELECT auth_hash FROM groups WHERE group_id=?", (group_id,)
            ).fetchone()
            if row is not None:
                # Idempotent iff the same auth_hash re-registers. A different
                # hash for an existing group is rejected: you cannot hijack a
                # group without the pairing secret.
                return hmac.compare_digest(row[0], auth_hash)
            self._conn.execute(
                "INSERT INTO groups(group_id, auth_hash, pairing_salt, created_at)"
                " VALUES (?,?,?,?)",
                (group_id, auth_hash, pairing_salt, time.time()),
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO seq_counter(group_id, seq) VALUES (?, 0)",
                (group_id,),
            )
            self._conn.commit()
            return True

    def get_group_auth_hash(self, group_id: str):
        with self._lock:
            row = self._conn.execute(
                "SELECT auth_hash FROM groups WHERE group_id=?", (group_id,)
            ).fetchone()
            return row[0] if row else None

    def upsert_records(self, group_id: str, records: list):
        """Optimistic-concurrency batch upsert (last-writer-wins by version).

        A record is accepted only if its version is strictly greater than the
        stored version. Stale writes are reported as conflicts with the current
        server version so the client can rebase. The whole batch is atomic.
        """
        accepted, conflicts = [], []
        with self._lock:
            try:
                self._conn.execute("BEGIN")
                srow = self._conn.execute(
                    "SELECT seq FROM seq_counter WHERE group_id=?", (group_id,)
                ).fetchone()
                seq = srow[0] if srow else 0
                for r in records:
                    coll, rid = r["collection"], r["id"]
                    ver = int(r["version"])
                    ex = self._conn.execute(
                        "SELECT version FROM records WHERE group_id=? AND"
                        " collection=? AND id=?", (group_id, coll, rid),
                    ).fetchone()
                    if ex is not None and ver <= ex[0]:
                        conflicts.append(
                            {"collection": coll, "id": rid,
                             "your_version": ver, "server_version": ex[0]}
                        )
                        continue
                    seq += 1
                    self._conn.execute(
                        "INSERT INTO records(group_id, collection, id, nonce,"
                        " ciphertext, version, tombstone, alg, seq)"
                        " VALUES (?,?,?,?,?,?,?,?,?)"
                        " ON CONFLICT(group_id, collection, id) DO UPDATE SET"
                        " nonce=excluded.nonce, ciphertext=excluded.ciphertext,"
                        " version=excluded.version, tombstone=excluded.tombstone,"
                        " alg=excluded.alg, seq=excluded.seq",
                        (group_id, coll, rid, r["nonce"], r["ciphertext"], ver,
                         1 if r.get("tombstone") else 0, r.get("alg", "unknown"),
                         seq),
                    )
                    accepted.append({"collection": coll, "id": rid, "version": ver})
                self._conn.execute(
                    "UPDATE seq_counter SET seq=? WHERE group_id=?", (seq, group_id)
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return {"accepted": accepted, "conflicts": conflicts, "server_seq": seq}

    def query_records(self, group_id: str, collection, since: int):
        with self._lock:
            sql = ("SELECT collection, id, nonce, ciphertext, version, tombstone,"
                   " alg, seq FROM records WHERE group_id=? AND seq>?")
            params = [group_id, since]
            if collection:
                sql += " AND collection=?"
                params.append(collection)
            sql += " ORDER BY seq ASC"
            rows = self._conn.execute(sql, params).fetchall()
        recs = [
            {"collection": c, "id": i, "nonce": n, "ciphertext": ct,
             "version": v, "tombstone": bool(t), "alg": a, "seq": s}
            for (c, i, n, ct, v, t, a, s) in rows
        ]
        max_seq = recs[-1]["seq"] if recs else since
        return {"records": recs, "server_seq": max_seq}

    def close(self):
        with self._lock:
            self._conn.close()


# --- Auth -------------------------------------------------------------------
#
# The server stores auth_hash = SHA-256(k_auth), never k_auth itself.
#
# Each authenticated request carries two header values:
#   X-Sync-Group : the group_id
#   X-Sync-Token : k_auth (base64url)         <- proof-of-knowledge
#   X-Sync-Proof : HMAC-SHA256(k_auth, transcript) (base64url)  <- request binding
#
# Verification:
#   1. SHA-256(presented k_auth) == stored auth_hash    (constant-time compare)
#   2. HMAC(k_auth, method || "\n" || path || "\n" || SHA256(body)) == proof
#
# Property: the DB holds only SHA-256(k_auth). k_auth is a 256-bit
# HKDF-derived value, so the hash is a one-way commitment — a stolen database
# does not reveal k_auth and therefore cannot forge requests or (crucially)
# decrypt anything, since k_auth is unrelated to the encryption key beyond both
# descending from the client-only root key. See PROTOCOL.md §Auth.

def verify_request(store, group_id, token_b64, proof_b64, method, path, body):
    stored = store.get_group_auth_hash(group_id)
    if stored is None:
        return False
    try:
        k_auth = _b64u_dec(token_b64)
    except Exception:
        return False
    presented_hash = _b64u(hashlib.sha256(k_auth).digest())
    if not hmac.compare_digest(stored, presented_hash):
        return False
    transcript = (method.encode() + b"\n" + path.encode() + b"\n"
                  + hashlib.sha256(body).digest())
    expected_proof = _b64u(hmac.new(k_auth, transcript, hashlib.sha256).digest())
    try:
        return hmac.compare_digest(expected_proof, proof_b64)
    except Exception:
        return False


# --- base64url helpers (kept local so the server has no client dependency) ---

import base64  # noqa: E402


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_dec(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


# --- HTTP handler -----------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "T3dmiumSync/1.0"
    protocol_version = "HTTP/1.1"

    # The store is attached to the server instance.
    @property
    def store(self) -> Store:
        return self.server.store

    # Silence default request logging: we never want record metadata in logs.
    def log_message(self, *args):
        pass

    def _send(self, status: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > MAX_BODY:
            return None
        return self.rfile.read(length) if length else b""

    # -- routing --
    def do_POST(self):
        parsed = urlparse(self.path)
        body = self._read_body()
        if body is None:
            return self._send(413, {"error": "request too large"})
        if parsed.path == "/v1/pair":
            return self._handle_pair(body)
        if parsed.path == "/v1/records":
            return self._handle_push(parsed, body)
        return self._send(404, {"error": "not found"})

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/v1/records":
            return self._handle_pull(parsed)
        if parsed.path == "/v1/health":
            return self._send(200, {"status": "ok"})
        return self._send(404, {"error": "not found"})

    # -- endpoints --
    def _handle_pair(self, body: bytes):
        # Pairing is intentionally UNauthenticated: it registers a brand-new
        # group. It cannot overwrite an existing group with a different secret
        # (create_group rejects that), so an attacker gains nothing.
        try:
            payload = json.loads(body)
            group_id = payload["group_id"]
            auth_hash = payload["auth_hash"]
        except Exception:
            return self._send(400, {"error": "invalid pair payload"})
        pairing_salt = payload.get("pairing_salt")
        ok = self.store.create_group(group_id, auth_hash, pairing_salt)
        if not ok:
            return self._send(409, {"error": "group exists with different secret"})
        return self._send(200, {"group_id": group_id, "paired": True})

    def _authed(self, parsed, body):
        group_id = self.headers.get("X-Sync-Group", "")
        token = self.headers.get("X-Sync-Token", "")
        proof = self.headers.get("X-Sync-Proof", "")
        path = parsed.path if not parsed.query else parsed.path + "?" + parsed.query
        method = self.command
        if not group_id or not verify_request(
            self.store, group_id, token, proof, method, path, body
        ):
            return None
        return group_id

    def _handle_push(self, parsed, body: bytes):
        group_id = self._authed(parsed, body)
        if group_id is None:
            return self._send(403, {"error": "authentication failed"})
        try:
            payload = json.loads(body)
            records = payload["records"]
        except Exception:
            return self._send(400, {"error": "invalid records payload"})
        if not isinstance(records, list) or len(records) > MAX_RECORDS_PER_BATCH:
            return self._send(400, {"error": "bad batch"})
        for r in records:
            if not all(k in r for k in ("collection", "id", "nonce",
                                        "ciphertext", "version")):
                return self._send(400, {"error": "malformed record"})
        result = self.store.upsert_records(group_id, records)
        status = 200 if not result["conflicts"] else 409
        return self._send(status, result)

    def _handle_pull(self, parsed):
        group_id = self._authed(parsed, b"")
        if group_id is None:
            return self._send(403, {"error": "authentication failed"})
        q = parse_qs(parsed.query)
        collection = q.get("collection", [None])[0]
        try:
            since = int(q.get("since", ["0"])[0])
        except ValueError:
            since = 0
        return self._send(200, self.store.query_records(group_id, collection, since))


class SyncServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, store: Store):
        super().__init__(addr, Handler)
        self.store = store


def make_server(host: str, port: int, db_path: str):
    store = Store(db_path)
    return SyncServer((host, port), store)


def main():
    p = argparse.ArgumentParser(description="T3dmium zero-knowledge sync server")
    p.add_argument("--host", default="127.0.0.1",
                   help="bind address (default 127.0.0.1; do not expose "
                        "directly to the internet without a TLS reverse proxy)")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--db", default="data.db", help="sqlite path or :memory:")
    args = p.parse_args()
    srv = make_server(args.host, args.port, args.db)
    print("T3dmium sync server listening on http://%s:%d  (db=%s)"
          % (args.host, args.port, args.db))
    print("Plain HTTP — terminate TLS with your own reverse proxy for remote use.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        srv.store.close()


if __name__ == "__main__":
    main()
