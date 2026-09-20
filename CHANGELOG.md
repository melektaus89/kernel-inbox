# Changelog

## 0.1.4 — 2026-09-19

### Added

- A settings cog beside Refresh with Appearance, Feeds, and Categories sections.
- Desktop, Ethereal dark, and Light themes; reading text sizes; compact or comfortable message spacing; and an editable display timezone without rebuilding.
- Public RSS 2.0 and Atom subscriptions, alongside the nine built-in feeds. Add, rename, remove, restore built-in feeds, and move feeds between categories.
- Category creation, renaming, and removal. Removing a category keeps its feeds under Uncategorized.
- Custom-feed caching with saved-copy fallback, plain-text content, public-destination and redirect checks, and a 5 MB response limit.

### Changed

- Settings edits remain in a draft until Apply (save and stay open) or OK (save and close). Cancel, Escape, and closing the panel discard changes since the last Apply.
- Save controls and pending feed-removal counts remain visible while settings scrolls. Add feed is at the top of Feeds; category creation is above the category list.
- Invalid timezones, blank names, and unfinished additions prevent saving. Browser-storage failures preserve the draft and keep settings open.
- Preferences stay in the current browser. Existing read/starred state and pane widths are retained.

### Validation

- Added offline RSS/Atom parser, cache, URL validation, redirect, and HTTP endpoint tests; all 26 Python tests pass.
- Verified draft removal, Cancel/reopen, Apply, OK, storage failure, and timezone validation handlers, plus TypeScript checks and the production build.

### Updating

Stop Kernel Inbox, pull the latest source with `git pull`, run `npm ci` and `npm run build`, then restart it and refresh your browser. For the login service, use `systemctl --user stop kernel-inbox` before updating and `systemctl --user start kernel-inbox` afterward. No service reinstall is needed. Open the settings cog beside Refresh to customize your inbox.

This release includes the settings work developed locally as 0.1.3; there was no separate public 0.1.3 release.

## 0.1.2 — 2026-09-17

### Changed

- The sidebar and message reader now reach the edges of the window, with single vertical dividers and retained content padding.
- Both desktop dividers can be dragged to adjust the sidebar, message list, and reading pane widths. Minimum widths keep each pane usable.
- Pane widths are remembered in this browser across reloads and feed changes when browser storage is available.
- Dividers support keyboard resizing: focus a divider with Tab, then use the arrow keys.
- Narrow windows retain the compact mailbox/reader layout.

### Updating

Stop Kernel Inbox, pull the latest source with `git pull`, run `npm ci` and `npm run build`, then start it again and refresh your browser. For the login service, use `systemctl --user stop kernel-inbox` before updating and `systemctl --user start kernel-inbox` afterward.

## 0.1.1 — 2026-09-13

### Fixed

- The startup installer now safely replaces an existing service symlink with a generated service file. Previously, it could write through the link and overwrite the repository's template with machine-specific paths.
- Broken service symlinks are backed up and replaced without creating their missing targets.
- Existing backup files and symlinks, including broken links, are protected from overwrite.

### Documentation and tests

- Clarified that the service template must be installed through the provided script and starts Kernel Inbox at login.
- Added offline regression tests for fresh installs, regular files, service symlinks, broken links, and backup protection.

### Updating

After pulling this release, run `python3 scripts/install-service.py` from your checkout to install or repair the login service. If the installer reports an existing `.service.bak`, move that backup somewhere safe before retrying. Stop any manually started Kernel Inbox process before installing so port 8765 is available.

If a previous installer run already modified the tracked `kernel-inbox.service` template, preserve any intentional changes and restore the release's template before reinstalling. This fix prevents future overwrites; it does not automatically repair a modified checkout.
