# Changelog

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
