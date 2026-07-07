---
name: Privacy leak
about: Report unexpected network traffic — treated as a serious bug
title: "[privacy] "
labels: privacy, bug
assignees: ""
---

**Thank you for reporting this.** T3dmium's core guarantee is that the only
network traffic is user-initiated. Any request that does not fit that
guarantee is a serious bug, regardless of how harmless the destination looks.
These reports are prioritised over ordinary bugs.

## Environment

- T3dmium version / commit:
- Chromium version (from `chromium_version.txt`):
- Platform and OS version (e.g. macOS 14.5 arm64, Windows 11 x64):
- Built from source or (future) binary release:

## Destination

- Host(s) contacted (e.g. `update.googleapis.com`):
- Port / protocol if known (e.g. 443/HTTPS, QUIC):
- Request path or payload details, if captured:

## What triggered it

Exact steps from launch to the observed request. Please note:

- Fresh profile or existing profile?
- Was the browser idle, or were you interacting with it?
- Which settings differ from defaults (especially update checks, search
  suggestions, or the local blocklist)?

1.
2.
3.

## Evidence

Attach or paste what you captured. The most useful forms, in order:

- **mitmproxy** flow export or screenshot (the audit harness in `audit/`
  can help you set this up);
- Chromium **DevTools Network panel** export (HAR) or screenshot;
- Packet capture (tcpdump/Wireshark) or firewall/DNS logs.

Please redact anything personal (cookies, tokens, URLs you were visiting)
before attaching.

## Reproducibility

- [ ] Happens every time with the steps above
- [ ] Happens intermittently
- [ ] Seen once, not yet reproduced
