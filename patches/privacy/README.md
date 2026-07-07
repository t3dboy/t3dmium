# T3dmium privacy-default patches

Phase 3 patches that flip Chromium defaults toward privacy. Each patch here
is applied *after* the adopted degoogle (ungoogled-chromium / inox) set, and
has been validated to apply cleanly in series order against the pinned
Chromium `150.0.7871.46`.

## Shipped

| Patch | File touched | Default changed | From → To |
| --- | --- | --- | --- |
| `enable-do-not-track-by-default.patch` | `chrome/browser/ui/browser_ui_prefs.cc` | `kEnableDoNotTrack` profile pref | `false` → `true` |

`enable-do-not-track-by-default.patch` turns on the Do Not Track signal out
of the box. This one pref also drives Global Privacy Control: Chromium reads
`kEnableDoNotTrack` in `chrome/browser/renderer_preferences_util.cc` into the
`enable_do_not_track` renderer preference, and the network stack emits both
the `DNT: 1` request header and the `Sec-GPC: 1` header from that single
signal. So enabling this pref delivers DNT **and** GPC together.

## Deferred (not shipped)

- **Third-party cookie blocking** — *already done by the adopted set; no
  T3dmium patch needed.* The adopted inox patch
  `degoogle/extra/inox-patchset/0006-modify-default-prefs.patch` already
  changes the `kCookieControlsMode` default in
  `components/content_settings/core/browser/cookie_settings.cc` from
  `CookieControlsMode::kIncognitoOnly` to `CookieControlsMode::kBlockThirdParty`.
  A standalone T3dmium patch was authored, passed *isolated* validation
  against pristine sources, then failed *series* validation as
  "previously applied" — confirming the flip is redundant. Removed rather
  than shipped to avoid a duplicate hunk.

- **Global Privacy Control (standalone)** — *covered by DNT; no distinct pref
  to flip.* At this pin there is no separate `kEnableGpc` /
  `kGlobalPrivacyControl...` profile pref registered with its own default
  literal. GPC is emitted off the same `enable_do_not_track` renderer
  preference (see above), so the shipped DNT patch already turns GPC on.
  A separate patch would have nothing clean to change.

- **DuckDuckGo default search** — *deferred; fragile stacking, needs a build.*
  The prepopulated fallback engine is selected in
  `components/search_engines/template_url_prepopulate_data.cc`
  (`GetPrepopulatedFallbackSearch` passes `google.id`). Flipping that to
  DuckDuckGo would stack on the adopted search patches
  (`prepopulated-search-engines.patch` and the Google-removal work) and
  depends on the regional-engine machinery resolving a `duckduckgo` engine
  symbol in scope — neither of which can be verified without a full build.
  Per the Phase 3 plan, first-run search choice is better delivered through
  the first-run flow provided by the adopted `first-run-page.patch`, so no
  guessed/forced patch is shipped here.
