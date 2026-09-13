#!/usr/bin/env python3
"""Install the optional Linux systemd user service for this checkout."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def quote(value):
    # systemd performs specifier expansion even inside quotes.
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def render():
    if any(c in str(ROOT) + sys.executable for c in '\n\r'):
        raise ValueError('service paths cannot contain newlines')
    directory = str(ROOT).replace('\\', '\\x5c').replace('%', '%%')
    return (ROOT / 'kernel-inbox.service').read_text().replace('@PROJECT_DIR@', directory).replace('@PYTHON@', quote(sys.executable))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--print', action='store_true', dest='preview', help='print the service without installing it')
    args = parser.parse_args()
    if args.preview:
        print(render(), end='')
        return
    if sys.platform != 'linux' or not shutil.which('systemctl'):
        parser.error('this optional integration requires Linux with systemd')
    if not (ROOT / 'dist/client/index.html').is_file():
        parser.error('run npm ci and npm run build first')
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    destination = config / 'systemd/user/kernel-inbox.service'
    rendered = render()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        backup = destination.with_suffix('.service.bak')
        if backup.exists() or backup.is_symlink():
            parser.error(f'backup already exists: {backup}; move it before reinstalling')
        shutil.copy2(destination, backup, follow_symlinks=False)
        if destination.is_symlink():
            destination.unlink()
    destination.write_text(rendered)
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', '--now', 'kernel-inbox.service'], check=True)
    subprocess.run(['systemctl', '--user', 'restart', 'kernel-inbox.service'], check=True)
    print(f'Installed {destination}')


if __name__ == '__main__':
    main()
