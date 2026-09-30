#!/usr/bin/env bash

set -euo pipefail

SOURCE_DIRECTORY="${1:-Lab2}"
PORT="${2:-COM3}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

for directory in . "$SOURCE_DIRECTORY" lib; do
    source_directory="$SCRIPT_DIR/$directory"

    if [[ ! -d "$source_directory" ]]; then
        printf 'Skipping missing directory: %s\n' "$directory" >&2
        continue
    fi

    printf 'Uploading Python files from %s...\n' "$directory"
    (
        cd "$source_directory"
        mpfshell -nc "open $PORT; mput .*\\.py"
    )
done

printf 'Upload complete.\n'
