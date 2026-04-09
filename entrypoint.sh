#!/bin/sh
# Farm-Agent v3.0.0 — Minimal entrypoint
# All schema creation and data seeding is handled at runtime
# by Memory.init(). This script just executes the CMD.
exec "$@"