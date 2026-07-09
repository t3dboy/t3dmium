# T3dmium — Frequently Asked Questions

Short, honest answers. For the full detail, follow the links into
[docs/privacy-features.md](docs/privacy-features.md),
[docs/why-privacy-first.md](docs/why-privacy-first.md), and
[PRIVACY.md](PRIVACY.md).

## Is it really Chrome?

It's the real **Chromium** engine — the same open-source engine Chrome is built
on — pinned to version **150.0.7871.46**. So you get genuine Chrome-grade
rendering, performance, and web compatibility. What's different is that the
Google-facing plumbing (telemetry, sign-in, experiments, phone-home services)
has been removed. Pages that work in Chrome work in T3dmium.

## Do my extensions work?

Yes. T3dmium supports standard Chrome extensions. Because it's the same engine,
the extensions you're used to install and run normally.

## Does it block ads?

**Partly today, more later — here's the honest split.** T3dmium already removes a
large amount of tracking at the source: no Google telemetry, third-party cookies
blocked by default, referrers trimmed, storage partitioned, Do Not Track and
Global Privacy Control on by default. That cuts down a lot of cross-site
tracking.

But a **dedicated ad/tracker-blocking engine** (the kind that hides ads on a page
using filter lists like EasyList/EasyPrivacy) is **on the roadmap and not yet
shipped** in the downloadable build. In the meantime, you can install a
content-blocking extension if you want page-level ad blocking today.

## What search engine does it use?

**Not Google.** T3dmium ships with a non-Google default search engine, and you
can change it to whatever you prefer in settings. A first-run picker that lets
you choose (with **DuckDuckGo** as the suggested default) is planned but not yet
shipped. Search **suggestions** are off by default; if you turn them on, your
keystrokes go only to the search engine you chose — nowhere else.

## Is it really sending nothing to Google?

In the background, yes — nothing. The whole point of T3dmium is that it makes
**no** telemetry, analytics, experiment, crash-report, or component-update
request to Google or anyone else on its own. The only network traffic it
generates is traffic **you** start: loading a page you asked for, an update check
you opted into, or installing an extension you requested. See
[docs/privacy-features.md](docs/privacy-features.md) for the item-by-item list of
what was removed.

(Naturally, when you visit a website, your browser talks to *that* website — and
that site may include its own third-party requests. T3dmium can't stop a page you
chose to visit from loading; it stops *the browser itself* from phoning home.)

## How can I verify that myself?

Two ways:

1. **Read the source.** Everything is public at
   [github.com/t3dboy/t3dmium](https://github.com/t3dboy/t3dmium), including every
   patch applied to Chromium.
2. **Run the network audit.** The repo includes an automated harness (in
   [`audit/`](audit/), built on [mitmproxy](https://mitmproxy.org/)) that launches
   the browser behind a proxy, exercises it, and **fails if any request leaves the
   machine that wasn't user-initiated.** It runs in CI on every change, and you can
   run it against your own build. You can also point any network monitor
   (mitmproxy, Wireshark, Little Snitch) at T3dmium and watch it sit quiet.

## Why isn't it notarized or signed by Apple?

Apple notarization requires a **paid Apple Developer account**, which isn't part
of this independent open-source project. So the macOS build is **ad-hoc signed**
instead: macOS can verify the app hasn't been tampered with since it was signed,
but can't tie it to a registered developer. That's why you'll see a first-launch
warning and need to right-click → **Open** once. See [INSTALL.md](INSTALL.md) for
the exact steps.

## Is it safe?

The app is safe to run — but don't take that on faith, which is the whole
philosophy here. Because the **entire source and build process are public**, you
(or anyone) can audit exactly what T3dmium does, and the built-in network audit
demonstrates it isn't leaking data. Open-source auditability is a stronger
assurance than a signature you can't inspect. The trade-off is the extra
first-launch step described in [INSTALL.md](INSTALL.md).

## Why based on Chromium and not Firefox?

Two practical reasons. First, **compatibility and extensions**: Chromium renders
the modern web the way most sites are tested against, and supports the large
Chrome extension ecosystem. Second, **the patch-set model**: Chromium can be
de-Googled cleanly by applying a curated set of patches and build flags on top of
a pinned release (the approach pioneered by
[ungoogled-chromium](https://github.com/ungoogled-software/ungoogled-chromium)),
which keeps every change reviewable. This isn't a knock on Firefox — it's a
different project with a different goal. T3dmium's goal is a de-Googled, verified
Chromium.

## Is there a Windows, Linux, or Intel Mac version?

Not as a download yet. Today there is one prebuilt binary: **macOS on Apple
Silicon (arm64).** An **Intel (x86_64) macOS** build and a **Windows** build are
**planned but not yet available.** Linux isn't a current download target. If you
can't wait, you can build from source (a heavy, multi-hour job) — see
[BUILDING.md](BUILDING.md).

## How do updates work?

T3dmium does **not** auto-update in the background — silent background traffic is
exactly what the project avoids. To update, download the newest DMG from the
[Releases page](https://github.com/t3dboy/t3dmium/releases) and reinstall over the
old app. The intended long-term model is an **opt-in** update check that you turn
on and control, never a silent one.

## Who makes this?

T3dmium is an independent open-source project maintained by **Ted Roubour**
([@t3dboy](https://github.com/t3dboy)). It builds on the work of the
**ungoogled-chromium** authors and the **Chromium** project, and studied
**Brave** and **Cromite** as prior art. See the [README](README.md) credits for
attributions.
