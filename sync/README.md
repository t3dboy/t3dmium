# T3dmium Sync — self-hosted, end-to-end-encrypted sync

A **self-hostable, zero-knowledge sync server** for T3dmium. It stores your
bookmarks, history, and saved passwords as **opaque ciphertext only**. All
encryption and decryption happen on your devices; the server can never read
your data, your keys, or your passphrase.

**Nothing is hosted by the project.** There is no T3dmium sync cloud, no
account, no email, no password on a server somewhere. You run the server on
your own machine or VPS, and only your paired devices — which share a
passphrase you chose — can decrypt what it stores.

- Wire + crypto protocol: [`PROTOCOL.md`](PROTOCOL.md)
- Server: [`server/app.py`](server/app.py)
- Reference client library: [`client/reference_client.py`](client/reference_client.py)
- Tests: [`tests/test_sync.py`](tests/test_sync.py)
- Design record: [`../docs/adr/0006-self-hosted-encrypted-sync.md`](../docs/adr/0006-self-hosted-encrypted-sync.md)

---

## Security properties (short version)

- **Zero-knowledge server.** It only ever holds ciphertext, nonces, and a
  *hash* of the group auth token. A full server/database compromise reveals
  neither your data nor your keys.
- **Client-side E2E encryption.** Keys are derived from your passphrase on your
  device (PBKDF2 → HKDF → per-purpose keys) and never leave it.
- **No accounts.** Devices pair into a "sync group" via a shared secret; the
  server authenticates requests by proof-of-knowledge of a token, storing only
  its hash.
- **Honest crypto caveat.** The shipped reference AEAD is a stdlib-only
  `SHA-256-CTR + HMAC-SHA256` (encrypt-then-MAC) construction, because the
  Python standard library has neither AES-GCM nor ChaCha20-Poly1305. It is
  correct and dependency-free, but **production clients should use AES-256-GCM
  or XChaCha20-Poly1305** (via `cryptography`/libsodium). The protocol is
  cipher-agnostic — see [`PROTOCOL.md` §2.1](PROTOCOL.md). Likewise, Argon2id is
  the recommended KDF upgrade over the shipped PBKDF2.

Full threat model — what the server *can* and *cannot* see — is in
[`PROTOCOL.md` §6](PROTOCOL.md).

---

## Requirements

- **Python 3.9+** and its standard library. That's it — no `pip install`.
- Optional, for a hardened production client only: the `cryptography` package
  (see [`requirements.txt`](requirements.txt)).

---

## Run the server (self-hosting)

### Directly

```sh
cd sync/server
python3 app.py --host 127.0.0.1 --port 8787 --db data.db
```

By default it binds to **127.0.0.1** and speaks **plain HTTP**. It does *not*
terminate TLS — that is your job.

- **Localhost / same machine:** 127.0.0.1 is fine as-is.
- **Remote / VPS:** put a TLS-terminating reverse proxy (Caddy, nginx,
  Traefik…) in front of it and keep the app bound to 127.0.0.1 so only the
  proxy can reach it. Never expose the plain-HTTP port to the internet.

Example nginx snippet:

```nginx
server {
    listen 443 ssl;
    server_name sync.example.org;
    ssl_certificate     /etc/letsencrypt/live/sync.example.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sync.example.org/privkey.pem;
    location / { proxy_pass http://127.0.0.1:8787; }
}
```

### With Docker

```sh
cd sync
docker compose up -d          # binds 127.0.0.1:8787, persists the db in a volume
```

See [`Dockerfile`](Dockerfile) and [`docker-compose.yml`](docker-compose.yml).
The container also speaks plain HTTP on 127.0.0.1 — **TLS remains the
operator's responsibility** (front it with your own reverse proxy).

---

## How pairing works

1. **Device A** picks a strong **passphrase** and generates a random
   **pairing salt**. Together with a server URL, these three values are the
   "pairing code" you carry to your other devices (e.g. via QR/manual entry).
2. Device A derives its keys locally and calls `POST /v1/pair`, sending only
   the public `group_id` and `SHA-256(Kauth)` (plus the non-secret salt).
3. **Device B** enters the *same* passphrase, salt, and server URL. It derives
   the identical `group_id` and keys **independently** — no key material ever
   crosses the network — and can immediately pull and decrypt.

Anyone who lacks the passphrase (including the server operator, and including a
thief who steals the whole database) cannot decrypt anything.

### Try it with the reference client

```python
import sys; sys.path.insert(0, "client")
import reference_client as rc

SALT = b"pick-a-random-16-plus-byte-salt!"
keys = rc.derive_group_keys("your strong passphrase", SALT)
client = rc.SyncClient("http://127.0.0.1:8787", keys, pairing_salt=SALT)

client.pair()
rec = rc.encrypt_record(keys, "bookmarks", "bm-1",
                        b'{"title":"Example","url":"https://example.org"}',
                        version=1)
print(client.push([rec]))

pulled = client.pull(collection="bookmarks")
print(rc.decrypt_record(keys, pulled["records"][0]))   # -> your plaintext
```

---

## Run the tests

From the repo root:

```sh
python3 -m unittest discover -s sync/tests -v
```

The suite spins up a real server, does two-device round trips, and inspects the
SQLite file directly to prove your plaintext never touches disk and that only a
*hash* of the auth token is stored.

---

## Browser integration status

The browser-side client that wires this protocol into T3dmium's bookmark /
history / password stores is **deferred / experimental** until a T3dmium build
exists. What ships here is the server, the protocol, a proven reference client,
and the tests — the trustworthy foundation the browser integration will build
on. See the ADR for the rationale.
