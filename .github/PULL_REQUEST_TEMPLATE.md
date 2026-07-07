## Summary

What does this PR change, and why?

## Type of change

- [ ] Patch set (`patches/`)
- [ ] Build tooling (`tools/`, `flags.gn`, `downloads.ini`, lists)
- [ ] Audit harness (`audit/`)
- [ ] Platform packaging (`platforms/`)
- [ ] Documentation
- [ ] CI / workflows

## Privacy impact

- [ ] This change cannot generate any network traffic
- [ ] This change can generate network traffic, and:
  - [ ] PRIVACY.md has been updated to document it
  - [ ] The audit harness covers it

If you are unsure, say so here and we will work it out in review.

## Checks

- [ ] `python3 tools/check_conventions.py` passes
- [ ] `python3 tools/validate_patches.py --remote` passes
- [ ] New/modified patches were generated against the pinned Chromium
      sources (`chromium_version.txt`), not written by hand
- [ ] New/modified patches have the required `Description:` / `Origin:`
      header and are listed in `patches/series` in the correct order

## Testing

How did you verify the change? If you built locally, note the platform(s)
(macOS arm64/x86_64, Windows x64) and what you exercised.

## Notes for reviewers

Anything that needs particular attention, follow-up work, or context.
