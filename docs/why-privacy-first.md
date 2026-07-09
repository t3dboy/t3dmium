# Why privacy-first

This document is the *why* behind T3dmium: why background browser telemetry is
worth caring about, why "verified, not promised" is the idea the whole project
turns on, and — honestly — what T3dmium does and does not protect you from. For
the concrete list of features, see
[privacy-features.md](privacy-features.md).

## The problem: your browser talks about you when you're not looking

A web browser is the most-used app on most people's computers. It sees
everything: what you search, what you read, what you buy, who you talk to, what
you worry about at 2 a.m. That alone is a lot of trust to place in one program.

The catch with mainstream Chromium-based browsers is that the browser doesn't
just *see* all of this — a normal build actively **reports back**. Before you've
typed a single web address, a stock Chrome or Chromium install will typically:

- enrol your browser in remote **experiments** (fetching config that silently
  flips features on and off),
- upload **usage metrics** describing how you use it — sometimes keyed to the
  specific URLs you visit,
- **check in** for component updates on a schedule,
- be ready to **upload crash reports**,
- maintain a persistent **push-messaging** connection,
- and fetch **promotional** content and nags.

None of this is the page you asked for. It's the browser, on its own initiative,
talking to a third party about your machine and your behaviour. Most of it
happens invisibly, and most of it has no obvious off switch.

Individually, each ping seems small. Collectively, they're a continuous,
low-level stream of signals about you, flowing to infrastructure you don't
control — and you never explicitly agreed to any single one of them.

## The T3dmium stance: nothing in the background, ever

T3dmium's core position is simple and strict:

> **The only network traffic the browser generates is traffic you initiated.**

Loading a page you navigated to? That's you. An update check you switched on?
That's you. Installing an extension you chose? That's you. Everything else — the
metrics, the experiments, the crash uploads, the check-ins, the push connection,
the promos — is **removed**, not merely reduced. See
[privacy-features.md](privacy-features.md) for the full teardown.

The design principle underneath: **features that trade your privacy for
convenience are off by default and clearly explained when you turn them on;
features that protect you are on by default.** You start protected and opt *into*
convenience, rather than starting exposed and having to hunt down settings to opt
out.

## Why "verified, not promised" is the whole point

Here is the uncomfortable truth about privacy claims: **anyone can make them.**
Every browser vendor says they respect your privacy. Privacy policies are written
by lawyers, updated quietly, and impossible for an ordinary person to check
against what the software actually does on the wire.

A promise you can't verify is just marketing.

So T3dmium's central commitment isn't only *"we don't phone home"* — it's *"and
you can prove it, and so can we, automatically, on every change."*

That proof is the **network-audit harness** in [`audit/`](../audit/). It:

1. launches the browser behind a [mitmproxy](https://mitmproxy.org/) proxy that
   records every request,
2. drives it through defined scenarios — a fresh profile, sitting idle,
   navigating to pages, opening settings screens,
3. and **fails the build** if it sees any request that a scripted user action
   didn't cause.

It runs in continuous integration, so a change that reintroduces a phone-home
gets caught before it can ship. And because everything is open source, **you can
run the exact same audit against your own build**, or point your own network
monitor at the browser and watch it stay silent.

This flips the trust model. You don't have to believe a policy document. You can
check the behaviour — and the project checks it for you on every commit. That is
the difference between *promised* and *verified*, and it's the reason T3dmium
exists in the form it does.

## The threat model: what T3dmium protects against — and what it doesn't

Being honest about scope is part of being trustworthy. T3dmium is a **de-Googled,
non-telemetry browser.** It is not a magic cloak of invisibility. Here's the
straight version.

### What T3dmium protects you from

- **The browser itself reporting on you.** No telemetry, analytics, experiment
  enrolment, crash uploads, RLZ, or component check-ins. The browser doesn't
  narrate your activity to Google or to the project.
- **Being tied to a Google identity.** No Google sign-in, Chrome Sync, or GAIA.
- **A lot of cross-site tracking.** Third-party cookies are blocked by default,
  storage is partitioned per top-level site, referrers are trimmed, and Do Not
  Track + Global Privacy Control are on by default.
- **Standing out by browser choice.** The user-agent matches Chrome exactly, so
  you blend into the crowd rather than flagging yourself as a rare browser.
- **Surprise background connections.** Prediction/prefetch is conservative; push
  messaging, promo surfaces, and update pings are gone.

### What T3dmium does NOT do

- **It is not a VPN and does not hide your IP address.** Websites you visit still
  see your IP, and so does your internet provider. If you need to hide your
  network location, use a VPN or Tor *in addition to* T3dmium.
- **It can't stop a site you chose to visit from tracking you on its own pages.**
  When you load a website, your browser talks to that website, and that site may
  include its own scripts and third-party requests. T3dmium reduces cross-site
  linking, but it doesn't make you anonymous to a site you deliberately opened —
  and today it does **not yet** include a dedicated ad/tracker-blocking engine
  (that's on the roadmap; see [privacy-features.md](privacy-features.md)).
- **It doesn't protect you from what you log into.** If you sign into an account,
  that service knows it's you. No browser can change that.
- **It isn't a full anti-fingerprinting fortress.** The user-agent policy helps
  you blend in, but comprehensive fingerprinting resistance (canvas, fonts,
  timing, and so on) is a deep, separate problem T3dmium does not claim to fully
  solve.
- **It doesn't defend against malware you install** or against a compromised
  operating system. It's a browser, not endpoint security.

Put plainly: **T3dmium's job is to make sure your browser isn't the thing leaking
information about you.** It shrinks your exposure and proves it does so. It does
not, and cannot, make you anonymous on the internet by itself. Knowing exactly
where that line sits is part of using any privacy tool well — and we'd rather tell
you than let you assume.

## Why this approach, and why open source

T3dmium is built as a **reviewable patch set** on top of a **pinned** Chromium
release (the model pioneered by
[ungoogled-chromium](https://github.com/ungoogled-software/ungoogled-chromium)),
rather than as an opaque fork. That choice is itself a privacy decision: it keeps
every single change **visible and auditable**, and it pairs naturally with the
verification harness. Openness isn't a nice-to-have bolted on the side — it's the
mechanism that makes "verified, not promised" possible in the first place.

If you want to see the claims turned into code, read the patches in
[`patches/`](../patches/), the commitments in [PRIVACY.md](../PRIVACY.md), and the
audit in [`audit/`](../audit/).
