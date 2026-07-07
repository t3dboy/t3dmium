"""T3dmium sync — end-to-end test suite (pure stdlib unittest, Python 3.9).

Run from the repo root:
    python3 -m unittest discover -s sync/tests -v

These tests spin up a REAL server on a loopback port, drive it with the
reference client, and inspect the on-disk SQLite database to prove the server
is genuinely zero-knowledge.

Author: Ted Roubour
"""

import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import warnings

# socketserver's daemon request threads occasionally outlive a test and trip a
# cosmetic ResourceWarning about the accepted socket. It is harmless (the OS
# reclaims the fd on process exit) and unrelated to the code under test, so we
# quiet it to keep the verbose output readable.
warnings.filterwarnings("ignore", category=ResourceWarning)

# Make the sibling client/ and server/ importable regardless of CWD.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SYNC = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_SYNC, "client"))
sys.path.insert(0, os.path.join(_SYNC, "server"))

import reference_client as rc          # noqa: E402
import app as server_app               # noqa: E402


PASSPHRASE = "correct horse battery staple"
PAIRING_SALT = b"t3dmium-shared-pairing-salt-0001"   # non-secret, shared in group


class LiveServer:
    """Context helper: a real SyncServer on an ephemeral loopback port with a
    temp-file DB (so tests can also inspect the DB on disk)."""

    def __init__(self):
        self.tmpdir = tempfile.mkdtemp(prefix="t3dsync-")
        self.db_path = os.path.join(self.tmpdir, "data.db")
        self.server = server_app.make_server("127.0.0.1", 0, self.db_path)
        self.port = self.server.server_address[1]
        self.url = "http://127.0.0.1:%d" % self.port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.store.close()
        # best-effort cleanup
        for f in os.listdir(self.tmpdir):
            try:
                os.remove(os.path.join(self.tmpdir, f))
            except OSError:
                pass
        try:
            os.rmdir(self.tmpdir)
        except OSError:
            pass


def make_client(url, passphrase=PASSPHRASE, salt=PAIRING_SALT):
    keys = rc.derive_group_keys(passphrase, salt, iterations=50_000)
    return rc.SyncClient(url, keys, pairing_salt=salt)


class RoundTripTest(unittest.TestCase):
    def test_two_devices_same_passphrase_round_trip(self):
        with LiveServer() as srv:
            a = make_client(srv.url)
            a.pair()
            secret = b'{"title":"My Bank","url":"https://bank.example"}'
            rec = rc.encrypt_record(a.keys, "bookmarks", "bm-1", secret, version=1)
            res = a.push([rec])
            self.assertEqual(res["accepted"][0]["id"], "bm-1")
            self.assertEqual(res["conflicts"], [])

            # Device B: independent client, same passphrase + salt.
            b = make_client(srv.url)
            self.assertEqual(a.keys.group_id, b.keys.group_id)
            pulled = b.pull(collection="bookmarks")
            self.assertEqual(len(pulled["records"]), 1)
            plaintext = rc.decrypt_record(b.keys, pulled["records"][0])
            self.assertEqual(plaintext, secret)


class ZeroKnowledgeTest(unittest.TestCase):
    def test_plaintext_never_touches_disk(self):
        with LiveServer() as srv:
            a = make_client(srv.url)
            a.pair()
            secret = b"SUPER-SECRET-BOOKMARK-TITLE-DO-NOT-LEAK"
            rec = rc.encrypt_record(a.keys, "bookmarks", "bm-1", secret, version=1)
            a.push([rec])

            # Inspect the raw DB file bytes.
            with open(srv.db_path, "rb") as fh:
                raw = fh.read()
            self.assertNotIn(secret, raw)
            self.assertNotIn(b"SUPER-SECRET", raw)

            # And inspect via SQL: stored ciphertext must not decode to plaintext.
            conn = sqlite3.connect(srv.db_path)
            rows = conn.execute(
                "SELECT ciphertext, nonce FROM records"
            ).fetchall()
            conn.close()
            self.assertEqual(len(rows), 1)
            stored_blob = rc.b64u_dec(rows[0][0])
            self.assertNotIn(secret, stored_blob)

    def test_server_stores_only_auth_hash_not_token(self):
        with LiveServer() as srv:
            a = make_client(srv.url)
            a.pair()
            conn = sqlite3.connect(srv.db_path)
            row = conn.execute(
                "SELECT auth_hash FROM groups WHERE group_id=?",
                (a.keys.group_id,),
            ).fetchone()
            conn.close()
            self.assertIsNotNone(row)
            stored = row[0]
            # Stored value equals SHA-256(k_auth), NOT k_auth itself.
            self.assertEqual(stored, a.keys.auth_hash())
            self.assertNotEqual(stored, a.keys.auth_token())
            # The raw token must not appear anywhere in the DB file.
            with open(srv.db_path, "rb") as fh:
                raw = fh.read()
            self.assertNotIn(a.keys.k_auth, raw)
            # Nor should the encryption key.
            self.assertNotIn(a.keys.k_enc, raw)


class AuthTest(unittest.TestCase):
    def test_wrong_auth_token_rejected(self):
        with LiveServer() as srv:
            a = make_client(srv.url)
            a.pair()
            rec = rc.encrypt_record(a.keys, "bookmarks", "bm-1", b"x", version=1)
            a.push([rec])

            # Attacker knows the (public) group_id but has a bogus auth token.
            attacker = make_client(srv.url, passphrase="wrong-passphrase")
            # Force the attacker to target the victim's group id but keep its
            # own (wrong) auth material.
            attacker.keys.group_id = a.keys.group_id
            with self.assertRaises(rc.SyncError) as ctx:
                attacker.pull()
            self.assertIn(ctx.exception.status, (401, 403))

    def test_pull_unknown_group_rejected(self):
        with LiveServer() as srv:
            a = make_client(srv.url)  # never paired
            with self.assertRaises(rc.SyncError) as ctx:
                a.pull()
            self.assertIn(ctx.exception.status, (401, 403))

    def test_constant_time_compare_used(self):
        # Assert the server module actually uses hmac.compare_digest.
        src = open(os.path.join(_SYNC, "server", "app.py")).read()
        self.assertIn("hmac.compare_digest", src)

    def test_pair_cannot_hijack_existing_group(self):
        with LiveServer() as srv:
            a = make_client(srv.url)
            a.pair()
            # Different passphrase => different auth_hash, same group_id forced.
            imposter = make_client(srv.url, passphrase="different")
            imposter.keys.group_id = a.keys.group_id
            with self.assertRaises(rc.SyncError) as ctx:
                imposter.pair()
            self.assertEqual(ctx.exception.status, 409)


class ConcurrencyTest(unittest.TestCase):
    def test_stale_version_reported_as_conflict(self):
        with LiveServer() as srv:
            a = make_client(srv.url)
            a.pair()
            r1 = rc.encrypt_record(a.keys, "bookmarks", "bm-1", b"v2", version=2)
            res = a.push([r1])
            self.assertEqual(res["conflicts"], [])

            # A stale write at version 1 must be rejected as a conflict.
            r_stale = rc.encrypt_record(a.keys, "bookmarks", "bm-1", b"v1",
                                        version=1)
            res2 = a.push([r_stale])
            self.assertEqual(len(res2["conflicts"]), 1)
            self.assertEqual(res2["conflicts"][0]["server_version"], 2)
            self.assertEqual(res2["accepted"], [])

    def test_last_writer_wins_higher_version(self):
        with LiveServer() as srv:
            a = make_client(srv.url)
            a.pair()
            a.push([rc.encrypt_record(a.keys, "bookmarks", "bm-1", b"old",
                                      version=1)])
            a.push([rc.encrypt_record(a.keys, "bookmarks", "bm-1", b"new",
                                      version=2)])
            b = make_client(srv.url)
            pulled = b.pull(collection="bookmarks")
            self.assertEqual(len(pulled["records"]), 1)
            self.assertEqual(pulled["records"][0]["version"], 2)
            self.assertEqual(rc.decrypt_record(b.keys, pulled["records"][0]),
                             b"new")


class TombstoneTest(unittest.TestCase):
    def test_tombstone_delete_propagates(self):
        with LiveServer() as srv:
            a = make_client(srv.url)
            a.pair()
            a.push([rc.encrypt_record(a.keys, "bookmarks", "bm-1", b"alive",
                                      version=1)])
            # Delete = a higher-version tombstone record.
            a.push([rc.encrypt_record(a.keys, "bookmarks", "bm-1", b"",
                                      version=2, tombstone=True)])
            b = make_client(srv.url)
            pulled = b.pull(collection="bookmarks")
            self.assertEqual(len(pulled["records"]), 1)
            self.assertTrue(pulled["records"][0]["tombstone"])
            # A tombstone still authenticates and decrypts to empty bytes.
            self.assertEqual(rc.decrypt_record(b.keys, pulled["records"][0]), b"")


class AeadTamperTest(unittest.TestCase):
    def test_tampered_ciphertext_fails(self):
        keys = rc.derive_group_keys(PASSPHRASE, PAIRING_SALT, iterations=50_000)
        rec = rc.encrypt_record(keys, "c", "id", b"payload", version=1)
        blob = bytearray(rc.b64u_dec(rec["ciphertext"]))
        blob[0] ^= 0x01
        rec["ciphertext"] = rc.b64u(bytes(blob))
        with self.assertRaises(ValueError):
            rc.decrypt_record(keys, rec)

    def test_tampered_nonce_fails(self):
        keys = rc.derive_group_keys(PASSPHRASE, PAIRING_SALT, iterations=50_000)
        rec = rc.encrypt_record(keys, "c", "id", b"payload", version=1)
        nonce = bytearray(rc.b64u_dec(rec["nonce"]))
        nonce[0] ^= 0xFF
        rec["nonce"] = rc.b64u(bytes(nonce))
        with self.assertRaises(ValueError):
            rc.decrypt_record(keys, rec)

    def test_tampered_aad_field_fails(self):
        # Changing version (part of AAD) without re-encrypting breaks the tag.
        keys = rc.derive_group_keys(PASSPHRASE, PAIRING_SALT, iterations=50_000)
        rec = rc.encrypt_record(keys, "c", "id", b"payload", version=1)
        rec["version"] = 99
        with self.assertRaises(ValueError):
            rc.decrypt_record(keys, rec)


class WrongPassphraseTest(unittest.TestCase):
    def test_wrong_passphrase_cannot_decrypt(self):
        with LiveServer() as srv:
            a = make_client(srv.url)
            a.pair()
            secret = b"my private data"
            a.push([rc.encrypt_record(a.keys, "bookmarks", "bm-1", secret,
                                      version=1)])
            # A client with the same salt but wrong passphrase derives a
            # DIFFERENT group_id, so it cannot even find the group. To isolate
            # the crypto property, decrypt A's record with wrong-passphrase keys
            # directly.
            wrong = rc.derive_group_keys("not the passphrase", PAIRING_SALT,
                                         iterations=50_000)
            pulled = a.pull(collection="bookmarks")
            with self.assertRaises(ValueError):
                rc.decrypt_record(wrong, pulled["records"][0])
            # Server is unaffected: A can still decrypt.
            self.assertEqual(rc.decrypt_record(a.keys, pulled["records"][0]),
                             secret)


class KdfTest(unittest.TestCase):
    def test_derivation_is_deterministic_and_separated(self):
        k1 = rc.derive_group_keys(PASSPHRASE, PAIRING_SALT, iterations=50_000)
        k2 = rc.derive_group_keys(PASSPHRASE, PAIRING_SALT, iterations=50_000)
        self.assertEqual(k1.k_enc, k2.k_enc)
        self.assertEqual(k1.group_id, k2.group_id)
        # Domain separation: the three sub-keys differ from each other.
        self.assertNotEqual(k1.k_enc, k1.k_mac)
        self.assertNotEqual(k1.k_enc, k1.k_auth)
        self.assertNotEqual(k1.k_mac, k1.k_auth)


if __name__ == "__main__":
    unittest.main()
