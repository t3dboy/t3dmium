# T3dmium Privacy Features — the plain-English rundown

This is the detailed, human-readable tour of what T3dmium removes, what it turns
off, and what it turns on to protect you — and, just as importantly, **why each
one matters.** If you want the strictly authoritative, service-by-service table
(with implementation status per phase), see [PRIVACY.md](PRIVACY.md). If you want
the philosophy behind all of this, see
[why-privacy-first.md](why-privacy-first.md).

**A note on "shipped now" vs. "planned."** T3dmium is honest about what's in the
build today versus what's on the roadmap. Each item below is labelled. Everything
in the **de-Google removal set** and the core **protective defaults** (Do Not
Track + GPC, third-party cookie blocking) is **shipped now.** A dedicated
ad/tracker-blocking engine and a first-run search picker are **planned.**

---

## Part 1 — What's removed or neutralized

Modern Chromium contacts Google for dozens of reasons that have nothing to do
with loading the page you asked for. Here's each one, in plain terms.

### Google account sign-in / Chrome Sync / GAIA — *removed*

**What it normally does:** lets you sign into the browser with a Google account
and sync your history, passwords, tabs, and settings to Google's servers.

**Why it matters for privacy:** it ties your entire browsing life to a Google
identity stored on Google's infrastructure.

**What T3dmium does:** removes it entirely. There is no Google sign-in, no Chrome
Sync, and no GAIA (Google's authentication system) anywhere in the browser.

### Safe Browsing pings — *removed; optional fully-local blocklist planned*

**What it normally does:** as you browse, Chrome checks URLs against Google's Safe
Browsing service to warn about phishing and malware — which can involve sending
information about the sites you visit to Google.

**Why it matters:** it's a continuous stream of "where I'm going" signals to a
third party.

**What T3dmium does:** removes the remote Safe Browsing pings. A **replacement
that is fully local** — a blocklist checked entirely on your own machine, so no
URLs or hashes ever leave it — is **planned, off by default,** and will be clearly
explained in the UI when you enable it.

### Field trials / Finch / variations — *removed*

**What it normally does:** Chrome downloads an "experiment configuration" that
silently turns features on or off for your browser, so Google can run A/B tests
across the user base.

**Why it matters:** it means your browser fetches instructions from Google, and
different users quietly run different code.

**What T3dmium does:** removes it. Nothing is fetched, and **every user runs the
exact same code with the exact same defaults.** No hidden experiments.

### Component updater phone-home — *removed / neutralized*

**What it normally does:** a background service periodically checks in with Google
to update small "components" (certificate lists, filter data, and so on).

**Why it matters:** it's regular background traffic to Google that you never asked
for.

**What T3dmium does:** removes the background check-in. Data that used to be
fetched at runtime is instead shipped **inside each release**, so there's nothing
to phone home for.

### Crash reporting (Crashpad uploads) — *removed*

**What it normally does:** when the browser crashes, it can upload a crash report
to Google.

**Why it matters:** crash reports can contain fragments of what you were doing.

**What T3dmium does:** removes the upload path. If T3dmium crashes, the report is
written **locally only** and never transmitted anywhere.

### UMA / UKM usage metrics — *removed*

**What it normally does:** "Usage Metrics" and "URL-Keyed Metrics" report how you
use the browser (features used, timings, and in the case of UKM, activity keyed to
specific URLs) back to Google.

**Why it matters:** this is the core telemetry pipeline — a detailed picture of
your behaviour.

**What T3dmium does:** removes it completely. No usage metrics are collected or
sent, at all.

### RLZ tracking — *removed*

**What it normally does:** RLZ encodes information about how you obtained the
browser and your early usage into a token sent to Google (historically used to
measure promotions).

**What T3dmium does:** removes it entirely.

### Omnibox search-suggestion pings — *off by default*

**What it normally does:** as you type in the address bar, each keystroke can be
sent to a search provider to fetch live suggestions.

**Why it matters:** it can stream what you're typing — before you even hit
Enter — to a remote server.

**What T3dmium does:** **off by default.** If you choose to turn suggestions on,
your keystrokes go **only to the search engine you selected**, and never to Google
or any other party.

### Network prediction / preconnect / prefetch / DNS prefetch — *off / conservative*

**What it normally does:** to feel faster, Chrome guesses where you might go next
and connects, downloads, or resolves DNS ahead of time.

**Why it matters:** prediction can cause your browser to contact servers you never
actually chose to visit.

**What T3dmium does:** keeps these **off or conservative** by default and fully
under your control, so nothing is fetched on your behalf without your setting
saying so.

### Translate service pings — *removed*

**What it normally does:** the built-in translate feature can send page text and
language signals to Google's translation service.

**What T3dmium does:** removes the remote translate service and its ranking model.

### Spellcheck download service — *removed; dictionaries local*

**What it normally does:** Chrome can use a Google-hosted spellcheck service and
download dictionaries from Google.

**What T3dmium does:** removes the download service. **Dictionaries are bundled
locally** with the browser, so spellcheck works without contacting anyone.

### Promotions / "What's New" / default-browser nags / feed surfaces — *removed*

**What it normally does:** Chrome fetches and shows promotional content, "What's
New" pages, prompts to make it your default browser, and content feeds.

**Why it matters:** these surfaces fetch remote content and are a channel for
nudging behaviour.

**What T3dmium does:** removes them. No promotional content is fetched or shown.

### Google Cloud Messaging (GCM/FCM) push — *removed*

**What it normally does:** maintains a persistent connection to Google's push
messaging service.

**Why it matters:** it's an always-on background link to Google.

**What T3dmium does:** removes it. No GCM/FCM connection is ever established.

### Baked-in Google API keys — *none*

**What it normally does:** builds of Chrome ship with API keys that unlock Google
services.

**What T3dmium does:** ships with **no Google API keys** baked in. The doors to
those services aren't just closed — there's no key on the ring.

### Default search engine is not Google — *shipped (first-run picker planned)*

**What T3dmium does:** the default search engine is **not Google.** You can set it
to whatever you like. A **first-run picker** — offering a clear choice with
**DuckDuckGo** suggested as the default — is **planned but not yet shipped.**

---

## Part 2 — Protections that are turned ON

Removing traffic is half the job. T3dmium also enables defaults that actively
protect you.

### Do Not Track (DNT) + Global Privacy Control (GPC) — *ON by default*

**What they are:** two signals your browser sends to websites. **Do Not Track**
(`DNT: 1`) asks sites not to track you. **Global Privacy Control** (`Sec-GPC: 1`)
is a newer signal that, in some jurisdictions, carries legal weight as an opt-out
of the sale or sharing of your data.

**What T3dmium does:** both are **ON by default**, driven by a single preference.
You're opted out from the very first launch, without hunting through settings.
(Honesty check: these are *requests* — a site still has to honour them. GPC has
real legal force in some places; DNT is widely ignored. They cost you nothing and
help where they're respected.)

### Third-party cookie blocking — *ON by default*

**What it is:** third-party cookies are the classic tool for following you from
site to site to build an advertising profile.

**What T3dmium does:** **blocks them by default.** Cross-site tracking cookies
don't get set, so the most common cross-site tracking mechanism simply doesn't
work.

### Referrer trimming — *ON*

**What it is:** the "referrer" header tells a site which page you came from —
sometimes including detailed URLs that leak information.

**What T3dmium does:** trims cross-site referrers so sites see much less about
where you came from.

### Partitioned storage — *ON*

**What it is:** normally, a third-party embedded on many sites can use shared
storage to link your activity across all of them.

**What T3dmium does:** **partitions storage by the top-level site** you're
visiting. A tracker embedded on Site A and Site B gets a **separate, isolated**
storage bucket on each, so it can't join them together.

### User-agent matches Chrome exactly — *ON*

**What it is:** the "user-agent" is a string your browser announces in every
request identifying what browser you are.

**Why it matters:** if T3dmium announced itself as a rare, niche browser, that
uniqueness would make you *easier* to fingerprint and single out.

**What T3dmium does:** its user-agent **matches Chrome's exactly** for the pinned
version, with **no T3dmium token** or other unique marker. You blend into the
enormous Chrome crowd instead of standing out — the fingerprint-resistant choice.

---

## Part 3 — On the roadmap (not yet shipped)

Being upfront about what isn't here yet:

- **Dedicated ad / tracker-blocking engine.** Page-level ad blocking driven by
  filter lists (EasyList / EasyPrivacy), with lists pinned in each release and
  updated **only when you ask** — never in the background. The list handling and
  audit scenario are in place; the blocking engine itself is **planned.** Until it
  ships, a content-blocking extension covers this need.
- **First-run DuckDuckGo search picker.** A clear choice of default search engine
  at first launch. The default is already non-Google; the **picker UI is
  planned.**
- **Optional fully-local Safe Browsing blocklist.** A malware/phishing blocklist
  checked entirely on your machine, off by default. **Planned.**

---

## How you can check all of this

You never have to take the above on trust:

- **Read the patches.** Every change to Chromium lives in
  [`patches/`](../patches/) in the public repo.
- **Run the network audit.** The [`audit/`](../audit/) harness (built on
  [mitmproxy](https://mitmproxy.org/)) launches the browser, drives it through
  scenarios, and **fails if any non-user-initiated request escapes.** It runs in
  CI and you can run it locally.
- **Watch it yourself.** Point mitmproxy, Wireshark, or Little Snitch at T3dmium
  and observe how quiet it is when you're not actively doing something.

If you ever catch T3dmium making a request it shouldn't, that's a serious bug —
please report it with the
[privacy leak template](../.github/ISSUE_TEMPLATE/privacy_leak.md).
