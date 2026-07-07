# ADR-0006: Self-hosted, zero-knowledge, end-to-end-encrypted sync

**Status:** accepted (2026-07-07)

## Context

T3dmium users want their bookmarks, history, and saved passwords on more than
one device, but the fork's entire premise is that no third party — least of all
us — gets to see their browsing. Chrome Sync is the anti-pattern: it ties sync
to a Google account, and while it offers an optional passphrase, the default
routes plaintext-equivalent data through servers the vendor controls, under an
identity the vendor owns. That is exactly the trust relationship T3dmium exists
to sever.

We need a sync mechanism that a privacy-first fork can honestly stand behind:
no accounts, no vendor-held data, and no way for the storage operator (even when
that operator is us, or an attacker who has stolen the whole database) to read
anything.

## Decision

Ship a **self-hosted, zero-knowledge, client-side end-to-end-encrypted** sync
server. Specifically:

- **The server is a dumb blob store.** It stores opaque ciphertext plus a hash
  of a group auth token, and nothing else of value. All encryption, decryption,
  and key derivation happen client-side. See `sync/PROTOCOL.md`.
- **No accounts.** Devices pair into a "sync group" from a shared passphrase +
  salt; keys are derived on-device and never transmitted. The server
  authenticates by proof-of-knowledge of a token whose hash it stores.
- **Nothing is hosted by the project.** Users run their own server (binary,
  Docker, or behind their own TLS proxy). There is no T3dmium sync cloud.
- **The browser-side client integration is deferred/experimental** until a
  T3dmium build exists to integrate it into. What ships now is the server, the
  protocol, a proven reference client, and a passing test suite.

### Stdlib-crypto-for-reference vs. production-AES tradeoff

The local development machine and the reference test suite are constrained to
the Python 3.9 standard library (no `pip`). The stdlib has neither AES-GCM nor
ChaCha20-Poly1305. Rather than fake it or pull in a dependency the reference
cannot guarantee, the shipped reference AEAD is an honest, documented
**encrypt-then-MAC** construction: `SHA-256-CTR` keystream + `HMAC-SHA256` tag,
built from `hashlib`/`hmac`. Likewise the shipped KDF is `PBKDF2-HMAC-SHA256`.

This is a deliberate *reference* choice, not the recommended production cipher.
The wire protocol is cipher- and KDF-agnostic (records and the pairing payload
carry `alg`/`kdf` labels), so a production client SHOULD swap in **AES-256-GCM
or XChaCha20-Poly1305** and **Argon2id** via `cryptography`/libsodium with **no
server change**. Correctness and honesty over cargo-culting a cipher we cannot
build and test on the reference toolchain.

## Consequences

- A server compromise — up to and including theft of the entire database —
  yields metadata (record counts, ciphertext sizes, write timestamps, opaque
  slot labels, group activity) but never plaintext, keys, or the passphrase.
  The threat model states this leakage honestly (`PROTOCOL.md` §6).
- Users bear the operational cost of self-hosting and of adding TLS; the server
  speaks plain HTTP on 127.0.0.1 by design and expects an operator-run reverse
  proxy for remote use.
- Conflict handling is last-writer-wins by version with tombstones — simple and
  convergent, with no field-level merge. Richer semantics can be layered inside
  the encrypted payload, again with no server change.
- The reference implementation runs and its tests pass on stock Python 3.9 with
  zero third-party packages, keeping the trust surface auditable. The
  production hardening (real AEAD, Argon2id, optional challenge-response auth)
  is a client-side upgrade tracked against the future browser integration.
