# Changelog

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
