"""Seleção do cookie X11 sem abrir um display de verdade."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from hw_inventory.x11_session import (
    XAuthEntry,
    authority_matches,
    iter_xauth,
    pack_xauth,
    rekey_authority,
    select_xauthority,
)


class XAuthoritySelectionTest(unittest.TestCase):
    def test_mutter_cookie_when_home_xauthority_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_user = root / "run"
            run_user.mkdir()
            older = run_user / ".mutter-Xwaylandauth.old"
            newer = run_user / ".mutter-Xwaylandauth.new"
            older.write_bytes(b"old-cookie")
            newer.write_bytes(b"new-cookie")
            os.utime(older, (1_000_000_000, 1_000_000_000))
            os.utime(newer, (1_700_000_000, 1_700_000_000))
            home = root / "home"
            home.mkdir()

            chosen = select_xauthority(
                env_xauthority=str(home / ".Xauthority"),
                process_xauthority=None,
                run_user_dir=run_user,
                home=home,
            )

            self.assertEqual(chosen, newer)

    def test_rekey_binds_cookie_to_current_hostname(self) -> None:
        fake = b"\xab" * 16
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "server-auth"
            source.write_bytes(
                pack_xauth(XAuthEntry(256, b"PC01", b"0", b"MIT-MAGIC-COOKIE-1", fake))
            )
            dest = root / "rekeyed"

            rewritten = rekey_authority(source, ":0", "FOZ01", dest)
            entries = list(iter_xauth(dest.read_bytes()))

            self.assertEqual(rewritten, dest)
            self.assertEqual(len(entries), 1)
            self.assertFalse(authority_matches(source, ":0", "FOZ01"))
            self.assertTrue(authority_matches(dest, ":0", "FOZ01"))
            self.assertEqual(entries[0].address, b"FOZ01")
            self.assertEqual(entries[0].number, b"0")
            self.assertEqual(entries[0].data, fake)


if __name__ == "__main__":
    unittest.main()
