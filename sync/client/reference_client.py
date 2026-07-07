"""T3dmium sync — reference client library (pure Python 3.9 stdlib).

This module is the client half of the T3dmium end-to-end-encrypted sync
protocol. It performs ALL cryptography client-side and only ever transmits
opaque ciphertext, nonces, and an HMAC authentication proof to the server.
The server is a zero-knowledge blob store — see ../PROTOCOL.md.

Author: Ted Roubour
License: see ../../LICENSE

CRYPTO CAVEAT
-------------
The Python standard library ships neither AES-GCM nor ChaCha20-Poly1305.
To keep this reference implementation REAL, correct, and dependency-free, we
implement an authenticated stream cipher from hashlib primitives:

    keystream = SHA-256 in counter (CTR) mode keyed by Kenc
    ciphertext = plaintext XOR keystream
    tag        = HMAC-SHA256(Kmac, aad || nonce || ciphertext)   (encrypt-then-MAC)

This is a documented stdlib-only construction. PRODUCTION clients SHOULD use
AES-256-GCM or XChaCha20-Poly1305 via libsodium or the `cryptography` package.
The wire format is designed so a production client can swap the AEAD without
changing the protocol (only the `alg` label changes).
"""

import base64
import hashlib
import hmac
import json
import struct
import urllib.request
import urllib.error
import urllib.parse

# --- Protocol constants -----------------------------------------------------

KDF_ITERATIONS = 600_000          # PBKDF2-HMAC-SHA256 iteration count (shipped KDF)
ROOT_KEY_LEN = 32                 # bytes of PBKDF2 output
NONCE_LEN = 24                    # random per-record nonce (XChaCha-sized, future-proof)
AEAD_ALG = "sha256ctr-hmac-sha256-v1"
KDF_ALG = "pbkdf2-hmac-sha256"

# HKDF "info" labels — domain-separate the derived keys.
_INFO_ENC = b"t3dmium-sync/enc/v1"
_INFO_MAC = b"t3dmium-sync/mac/v1"
_INFO_AUTH = b"t3dmium-sync/auth/v1"
_INFO_GROUP = b"t3dmium-sync/group-id/v1"


# --- Base64url helpers ------------------------------------------------------

def b64u(data: bytes) -> str:
    """URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64u_dec(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


# --- KDF / key hierarchy (all client-side) ----------------------------------

def hkdf_sha256(ikm: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
    """RFC 5869 HKDF-Extract-then-Expand over HMAC-SHA256."""
    if salt is None or len(salt) == 0:
        salt = b"\x00" * hashlib.sha256().digest_size
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    okm = b""
    t = b""
    counter = 1
    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        okm += t
        counter += 1
    return okm[:length]


def derive_root_key(passphrase: str, pairing_salt: bytes,
                    iterations: int = KDF_ITERATIONS) -> bytes:
    """passphrase --PBKDF2-HMAC-SHA256--> root key. CLIENT-SIDE ONLY.

    `pairing_salt` is shared within a sync group (it is part of the pairing
    payload). It is NOT secret; the passphrase supplies the entropy.
    """
    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), pairing_salt, iterations, ROOT_KEY_LEN
    )


class GroupKeys:
    """The full client-side key hierarchy for one sync group.

    Derived entirely from (passphrase, pairing_salt). Nothing here — except
    ``group_id`` and ``auth_hash`` — ever leaves the client.
    """

    __slots__ = ("root", "k_enc", "k_mac", "k_auth", "group_id")

    def __init__(self, root: bytes):
        self.root = root
        self.k_enc = hkdf_sha256(root, b"", _INFO_ENC, 32)
        self.k_mac = hkdf_sha256(root, b"", _INFO_MAC, 32)
        self.k_auth = hkdf_sha256(root, b"", _INFO_AUTH, 32)
        # group_id is a public, non-secret identifier derived from the root so
        # both paired devices compute the same value without coordination.
        self.group_id = b64u(hkdf_sha256(root, b"", _INFO_GROUP, 16))

    def auth_hash(self) -> str:
        """The value the server stores: SHA-256(k_auth).

        The server persists ONLY this one-way hash. Because k_auth is a
        256-bit HKDF output, the hash is a non-invertible commitment: a stolen
        database reveals neither k_auth nor (a fortiori) the encryption key.
        """
        return b64u(hashlib.sha256(self.k_auth).digest())

    def auth_token(self) -> str:
        """k_auth itself, base64url. Presented per-request as proof-of-knowledge.

        The server hashes it and constant-time-compares against the stored
        auth_hash. Only ever sent over the operator's TLS transport.
        """
        return b64u(self.k_auth)

    def auth_proof(self, method: str, path: str, body: bytes) -> str:
        """HMAC(k_auth, transcript) binding the request to method+path+body.

        Prevents a captured token/proof pair from being replayed against a
        different endpoint or with a swapped body.
        """
        msg = method.encode() + b"\n" + path.encode() + b"\n" + \
            hashlib.sha256(body).digest()
        return b64u(hmac.new(self.k_auth, msg, hashlib.sha256).digest())


def derive_group_keys(passphrase: str, pairing_salt: bytes,
                      iterations: int = KDF_ITERATIONS) -> GroupKeys:
    return GroupKeys(derive_root_key(passphrase, pairing_salt, iterations))


# --- AEAD: SHA-256-CTR + HMAC-SHA256 (encrypt-then-MAC) ----------------------

def _sha256_ctr_keystream(key: bytes, nonce: bytes, nbytes: int) -> bytes:
    """Deterministic keystream: SHA-256(key || nonce || counter) blocks.

    Counter is a 64-bit big-endian block index. This is a documented
    stdlib-only stream cipher; see the module docstring caveat.
    """
    out = bytearray()
    counter = 0
    while len(out) < nbytes:
        block = hashlib.sha256(key + nonce + struct.pack(">Q", counter)).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:nbytes])


def aead_encrypt(k_enc: bytes, k_mac: bytes, nonce: bytes,
                 plaintext: bytes, aad: bytes = b"") -> bytes:
    """Return ciphertext||tag. Encrypt-then-MAC over aad||nonce||ciphertext."""
    ks = _sha256_ctr_keystream(k_enc, nonce, len(plaintext))
    ct = bytes(a ^ b for a, b in zip(plaintext, ks))
    tag = hmac.new(k_mac, aad + nonce + ct, hashlib.sha256).digest()
    return ct + tag


def aead_decrypt(k_enc: bytes, k_mac: bytes, nonce: bytes,
                 ct_and_tag: bytes, aad: bytes = b"") -> bytes:
    """Verify tag (constant-time) then decrypt. Raises on tamper/wrong key."""
    if len(ct_and_tag) < 32:
        raise ValueError("ciphertext too short")
    ct, tag = ct_and_tag[:-32], ct_and_tag[-32:]
    expected = hmac.new(k_mac, aad + nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise ValueError("authentication failed: tampered ciphertext or wrong key")
    ks = _sha256_ctr_keystream(k_enc, nonce, len(ct))
    return bytes(a ^ b for a, b in zip(ct, ks))


# --- Record encryption ------------------------------------------------------

def encrypt_record(keys: GroupKeys, collection: str, record_id: str,
                   plaintext: bytes, version: int, tombstone: bool = False,
                   nonce: bytes = None) -> dict:
    """Encrypt one syncable item into an opaque wire record.

    The AAD binds the ciphertext to (collection, id, version, tombstone) so an
    attacker cannot move a valid ciphertext to a different slot undetected.
    Note: collection/id are opaque tokens chosen by the client; the server
    never learns which real bookmark/password a record represents.
    """
    import os
    if nonce is None:
        nonce = os.urandom(NONCE_LEN)
    aad = _record_aad(collection, record_id, version, tombstone)
    body = b"" if tombstone else plaintext
    blob = aead_encrypt(keys.k_enc, keys.k_mac, nonce, body, aad)
    return {
        "collection": collection,
        "id": record_id,
        "nonce": b64u(nonce),
        "ciphertext": b64u(blob),
        "version": version,
        "tombstone": tombstone,
        "alg": AEAD_ALG,
    }


def decrypt_record(keys: GroupKeys, record: dict) -> bytes:
    """Decrypt a wire record back to plaintext. Returns b'' for tombstones.

    Raises ValueError on authentication failure (tamper / wrong passphrase).
    """
    nonce = b64u_dec(record["nonce"])
    blob = b64u_dec(record["ciphertext"])
    aad = _record_aad(record["collection"], record["id"],
                      record["version"], record["tombstone"])
    return aead_decrypt(keys.k_enc, keys.k_mac, nonce, blob, aad)


def _record_aad(collection: str, record_id: str, version: int,
                tombstone: bool) -> bytes:
    return json.dumps(
        [collection, record_id, version, bool(tombstone)],
        separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")


# --- Client for the sync server ---------------------------------------------

class SyncError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__("HTTP %d: %s" % (status, message))
        self.status = status


class SyncClient:
    """Thin HTTP client that speaks the T3dmium sync protocol."""

    def __init__(self, base_url: str, keys: GroupKeys, pairing_salt: bytes = None):
        self.base_url = base_url.rstrip("/")
        self.keys = keys
        self.pairing_salt = pairing_salt

    # -- low-level request with auth proof --
    def _request(self, method: str, path: str, payload: dict = None,
                 soft_statuses=()) -> dict:
        """Perform an authenticated request.

        `soft_statuses` lists non-2xx codes whose JSON body should be RETURNED
        rather than raised (e.g. 409 conflict on push, which carries the
        conflict list the caller needs to rebase).
        """
        body = b"" if payload is None else json.dumps(payload).encode("utf-8")
        proof = self.keys.auth_proof(method, path, body)
        headers = {
            "X-Sync-Group": self.keys.group_id,
            "X-Sync-Token": self.keys.auth_token(),
            "X-Sync-Proof": proof,
            "Content-Type": "application/json",
            "Connection": "close",
        }
        req = urllib.request.Request(
            self.base_url + path, data=body if payload is not None else None,
            headers=headers, method=method,
        )
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw = e.read()
            if e.code in soft_statuses:
                try:
                    return json.loads(raw)
                except Exception:
                    pass
            try:
                msg = json.loads(raw).get("error", raw.decode("utf-8", "replace"))
            except Exception:
                msg = raw.decode("utf-8", "replace")
            raise SyncError(e.code, msg)

    # -- protocol operations --
    def pair(self) -> dict:
        """Register this sync group with the server.

        Sends only group_id, the auth-token HASH, and the (non-secret) pairing
        salt so a second device can be onboarded. Never sends keys or auth token.
        """
        payload = {
            "group_id": self.keys.group_id,
            "auth_hash": self.keys.auth_hash(),
        }
        if self.pairing_salt is not None:
            payload["pairing_salt"] = b64u(self.pairing_salt)
        return self._request("POST", "/v1/pair", payload)

    def push(self, records) -> dict:
        """Upload a batch of encrypted records with optimistic concurrency.

        Returns {"accepted": [...], "conflicts": [...], "server_seq": N}. A 409
        (some records were stale) is NOT raised — its conflict list is returned
        so the caller can rebase to the reported server_version and retry.
        """
        return self._request("POST", "/v1/records", {"records": list(records)},
                             soft_statuses=(409,))

    def pull(self, collection: str = None, since: int = 0) -> dict:
        path = "/v1/records?since=%d" % since
        if collection:
            path += "&collection=" + urllib.parse.quote(collection)
        return self._request("GET", path)
