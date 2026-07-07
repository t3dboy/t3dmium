# T3dmium Sync Protocol

Version: 1 · Author: Ted Roubour

The T3dmium sync protocol lets a set of paired devices ("a sync group") share
bookmarks, history, and saved passwords through a **dumb, zero-knowledge blob
store**. The server never sees plaintext, never sees the encryption key, and
never learns which real item a record represents. All cryptography happens
**client-side**.

This document specifies the wire format and the cryptographic construction
precisely enough to build an interoperable client.

---

## 1. Key hierarchy (client-side only)

```
   passphrase  ──PBKDF2-HMAC-SHA256(salt=pairing_salt, iters=600000)──▶  root key (32 B)
       │
       └── root key ──HKDF-SHA256──┬──▶ Kenc     (encryption key,   info="t3dmium-sync/enc/v1")
                                   ├──▶ Kmac     (MAC key,          info="t3dmium-sync/mac/v1")
                                   ├──▶ Kauth    (auth token,       info="t3dmium-sync/auth/v1")
                                   └──▶ group_id (public identifier, info="t3dmium-sync/group-id/v1", 16 B, base64url)
```

- **passphrase** — chosen by the user; the sole source of entropy. Never
  transmitted, never stored anywhere.
- **pairing_salt** — a non-secret random value shared within the group. It is
  part of the pairing payload so a second device can derive identical keys. It
  is *not* secret; the passphrase supplies security.
- **root key** — `PBKDF2-HMAC-SHA256(passphrase, pairing_salt, 600000, dkLen=32)`.
  This is the **shipped, stdlib KDF**. PBKDF2 is memory-cheap; the
  **recommended production upgrade is Argon2id** (memory-hard), which the
  standard library does not provide. A production client SHOULD use Argon2id
  and advertise a different `kdf` label in the pairing payload.
- **Kenc, Kmac, Kauth** — 32-byte keys, domain-separated via HKDF `info`
  labels so no two are ever equal.
- **group_id** — derived from the root key so **both paired devices compute the
  same id without server coordination**. It is a public routing token; it
  reveals nothing about the passphrase or the data.

**Key derivation is entirely CLIENT-side.** The server receives only
`group_id` and `SHA-256(Kauth)`.

---

## 2. Record format

Each syncable item is encrypted client-side into an opaque wire record:

```json
{
  "collection": "bookmarks",         // opaque client-chosen bucket name
  "id":         "bm-42",             // opaque client-chosen record id
  "nonce":      "<base64url, 24 B>", // random per encryption
  "ciphertext": "<base64url>",       // AEAD output: ct || tag
  "version":    3,                   // monotonic per (collection,id); LWW key
  "tombstone":  false,               // true = deletion marker (empty plaintext)
  "alg":        "sha256ctr-hmac-sha256-v1"
}
```

- `collection` and `id` are **opaque tokens the client chooses**. The server
  treats them as routing labels only. A privacy-maximizing client MAY use
  random/blinded ids so the server cannot even tell two records belong to the
  same logical bookmark across renames.
- `version` is a monotonically increasing integer maintained by the client per
  `(collection, id)`. It drives conflict resolution (§4).
- `tombstone: true` records carry an authenticated **empty** plaintext; they
  propagate deletions (§4).

### 2.1 AEAD construction (the actually-implemented one)

The Python standard library ships **neither AES-GCM nor ChaCha20-Poly1305**.
To keep the reference implementation real, correct, and dependency-free, the
shipped AEAD is a documented **encrypt-then-MAC** construction built from
`hashlib`/`hmac`:

```
keystream  = SHA-256(Kenc || nonce || counter_be64)  for counter = 0,1,2,…   (CTR-style)
ciphertext = plaintext XOR keystream
tag        = HMAC-SHA256(Kmac, aad || nonce || ciphertext)                    (encrypt-then-MAC)
output     = ciphertext || tag        (tag is 32 bytes)
```

- **AAD** binds the ciphertext to its slot:
  `aad = json([collection, id, version, tombstone])` (compact, sorted). An
  attacker therefore cannot move a valid ciphertext to a different id/version
  without failing authentication.
- **Decryption** recomputes the tag and compares it in **constant time**
  (`hmac.compare_digest`) *before* deriving the keystream. A wrong passphrase
  yields a wrong Kmac and the tag check fails — no plaintext is ever produced.
- **Nonce** is 24 random bytes (XChaCha-sized, chosen so a production client can
  drop in XChaCha20-Poly1305 without a format change).

> **HONEST CAVEAT.** `SHA-256-CTR + HMAC-SHA256` is a *stdlib-only reference*
> AEAD. It provides confidentiality and integrity given full-entropy keys, but
> it is not a standardized/audited cipher. **Production clients SHOULD use
> AES-256-GCM or XChaCha20-Poly1305** via libsodium or the `cryptography`
> package, changing only the `alg` label. The protocol, wire format, key
> hierarchy, and server are all AEAD-agnostic; swapping the cipher requires no
> server change.

---

## 3. Endpoints

The server exposes a tiny HTTP/JSON API. All record endpoints require
authentication (§5). Pairing is intentionally unauthenticated.

### `POST /v1/pair`
Register a new sync group. Body:
```json
{ "group_id": "...", "auth_hash": "base64url(SHA-256(Kauth))", "pairing_salt": "base64url(...)" }
```
- First registration of a `group_id` wins and stores the `auth_hash` and salt.
- Re-registering the **same** `group_id` with the **same** `auth_hash` is
  idempotent (`200`). A different `auth_hash` for an existing group is rejected
  (`409`) — you cannot hijack a group without the pairing secret.
- Response: `{ "group_id": "...", "paired": true }`.

### `POST /v1/records`
Upload a batch of encrypted records (optimistic concurrency). Body:
`{ "records": [ <record>, … ] }` (max 1000 per batch, 8 MiB per request).
- Per record: accepted iff `version` is strictly greater than the stored
  version. Stale records are returned as conflicts.
- Response (`200` if no conflicts, `409` if some were stale):
```json
{
  "accepted":  [ {"collection":"...","id":"...","version":N}, … ],
  "conflicts": [ {"collection":"...","id":"...","your_version":N,"server_version":M}, … ],
  "server_seq": 1234
}
```

### `GET /v1/records?collection=&since=`
Download records changed since a sequence number.
- `since` — return only records with server `seq > since` (0 = everything).
  `seq` is a per-group monotonic change counter the server assigns on write; it
  lets a client resume an incremental pull.
- `collection` — optional filter.
- Response: `{ "records": [ <record>, … ], "server_seq": 1234 }`.

### Deletes
There is no DELETE verb. **Deletion is a tombstone**: push a record with the
same `(collection, id)`, a higher `version`, `tombstone: true`, and an
authenticated empty payload. Tombstones propagate like any other update and let
every device converge on the deletion. Operators MAY garbage-collect tombstones
older than a retention window out of band.

### `GET /v1/health`
Unauthenticated liveness probe → `{ "status": "ok" }`.

---

## 4. Conflict model — last-writer-wins by version, with tombstones

Each `(collection, id)` carries a client-maintained monotonic `version`.

- On push, the server accepts a record **iff `version > stored_version`**.
- A record whose `version <= stored_version` is **rejected as a conflict**; the
  response reports `server_version` so the client can rebase: re-encrypt its
  local change at `server_version + 1` (merging as its data model dictates) and
  retry.
- This is **last-writer-wins keyed by version number**, not wall-clock time, so
  it is robust to clock skew across devices. The client is responsible for
  advancing `version` past what it last saw.
- **Deletion** is just an LWW update whose winning value is a tombstone. A later
  re-creation simply uses a still-higher version.

This model is simple and converges. It does **not** do field-level merging;
richer CRDT semantics can be layered entirely client-side inside the encrypted
payload without any server change.

---

## 5. Authentication — proof-of-knowledge of Kauth

The server stores only `auth_hash = SHA-256(Kauth)`. Each authenticated request
carries three headers:

| Header          | Value                                                          |
|-----------------|----------------------------------------------------------------|
| `X-Sync-Group`  | `group_id`                                                     |
| `X-Sync-Token`  | `base64url(Kauth)` — proof-of-knowledge                        |
| `X-Sync-Proof`  | `base64url(HMAC-SHA256(Kauth, transcript))` — request binding  |

where `transcript = method || "\n" || path || "\n" || SHA-256(body)`.

Server verification:
1. Look up the stored `auth_hash` for `group_id`.
2. Compute `SHA-256(presented Kauth)` and **constant-time compare**
   (`hmac.compare_digest`) against `auth_hash`. Mismatch → `403`.
3. Recompute `HMAC-SHA256(Kauth, transcript)` and constant-time compare against
   `X-Sync-Proof`. Mismatch → `403`. This binds the credential to the exact
   method, path, and body, preventing replay against a different endpoint or a
   swapped body.

**Why store only the hash?** `Kauth` is a 256-bit HKDF output, so `SHA-256(Kauth)`
is a one-way commitment — a stolen database yields neither `Kauth` (so the thief
cannot forge writes) nor, crucially, anything that decrypts data, since `Kenc`
is a sibling key derived only on the client. The token is revealed to the
*server* per request; that is acceptable because the server is trusted to route,
not to decrypt, and the operator is expected to run it behind their own TLS. A
production deployment MAY upgrade to a challenge-response (server nonce) to avoid
sending `Kauth` at all; the current scheme keeps the reference minimal and
stateless.

---

## 6. Threat model — what the server can and cannot see

**The server CANNOT see:**
- plaintext of any bookmark, history entry, or password;
- the encryption key `Kenc`, MAC key `Kmac`, the passphrase, or the root key;
- which real item a record corresponds to (ids/collections are opaque tokens);
- enough from a database theft to decrypt anything or forge writes (it holds
  only ciphertext, nonces, and `SHA-256(Kauth)`).

**The server CAN see (state this honestly):**
- the number of records per group and per collection;
- the **size** of each ciphertext (leaks approximate plaintext length — pad
  client-side if this matters);
- **timestamps / sequence** of writes, i.e. sync-group activity patterns;
- the (opaque) `collection` and `id` labels, and hence update frequency of a
  given slot;
- the requesting IP and TLS metadata (mitigate with Tor/VPN if that matters);
- that a given `group_id` exists and how active it is.

**Trust boundary.** The client is trusted; the server is *honest-but-curious*
storage. Compromising the server yields metadata (counts, sizes, timing) but
not content or keys. Compromising a device or the passphrase yields everything
— protect the passphrase.

**Out of scope.** Traffic-analysis resistance, size-padding, and forward
secrecy across passphrase changes are not provided by the reference; they can
be added client-side. TLS is the operator's responsibility (§ README).
