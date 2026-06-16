#!/bin/bash
# Block direct pushes to refs/heads/main. Feature-branch pushes and tag pushes
# are allowed.
#
# Supports two invocation modes:
# 1. Native git pre-push hook: refspec lines on stdin
#    (format: local_ref local_sha remote_ref remote_sha)
# 2. pre-commit's pre-push stage: refspec info in PRE_COMMIT_REMOTE_BRANCH

set -euo pipefail

check_ref() {
  if [ "$1" = "refs/heads/main" ]; then
    echo "ERROR: Direct push to main is not allowed. Use a feature branch." >&2
    exit 1
  fi
}

if [ -n "${PRE_COMMIT_REMOTE_BRANCH:-}" ]; then
  check_ref "$PRE_COMMIT_REMOTE_BRANCH"
  exit 0
fi

while read -r _local_ref _local_sha remote_ref _remote_sha; do
  check_ref "$remote_ref"
done

exit 0
