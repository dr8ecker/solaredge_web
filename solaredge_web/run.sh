#!/bin/sh
set -eu
umask 077

# These fixed paths are private to the add-on; do not traverse user symlinks.
if [ -L /data ] || [ -L /data/runtime ] || [ -L /data/options.json ]; then
    echo 'ERROR: /data paths must not be symbolic links.' >&2
    exit 2
fi
install -d -m 0700 -o scraper -g scraper /data /data/runtime
if [ -f /data/options.json ]; then
    chown scraper:scraper /data/options.json
    chmod 0600 /data/options.json
fi
exec gosu scraper "$@"
