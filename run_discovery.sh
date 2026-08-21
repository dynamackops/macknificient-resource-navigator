#!/usr/bin/env bash
# Wrapper for cron: runs the Discovery & Vetting Agent's full pass
# (verify existing resources, then discover new candidates) and logs
# output. Portable to wherever the repo is cloned — resolves its own
# directory rather than assuming a fixed path.
#
# Install with (edit the schedule as you like; this runs weekly,
# Monday 6am local time):
#
#   crontab -e
#   0 6 * * 1 /path/to/macknificient-resource-navigator/run_discovery.sh
#
# (run `pwd` inside the repo to get the absolute path for that line)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

mkdir -p logs
LOG_FILE="logs/discovery_$(date +%Y%m%d_%H%M%S).log"

source venv/bin/activate
python3 discovery_agent.py full --limit 8 >> "$LOG_FILE" 2>&1
