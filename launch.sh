#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROFILE="${1:-balanced}"
"$DIR/.venv/bin/python" "$DIR/main.py" --profile "$PROFILE"