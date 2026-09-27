#!/bin/sh
set -eu
python -m ciri bootstrap
exec "$@"
