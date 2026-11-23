#!/usr/bin/env bash
# Replace the history of origin/main with one commit holding the current state.
#
#   tools/squash.sh "Commit message"
#
# Commits everything in the working tree as the single commit on main,
# force-pushes it (only if origin/main is still where we last saw it), deletes
# every other branch on origin and locally, expires the reflog and gc's, then
# dispatches the pages and image workflows, which the path filters would
# otherwise skip after a force-push. See CLAUDE.md.
set -euo pipefail

msg="${1:?usage: tools/squash.sh \"commit message\"}"
cd "$(git rev-parse --show-toplevel)"

git fetch --quiet origin
expected="$(git rev-parse origin/main)"
echo "origin/main is $expected; it will be replaced"

git checkout -q --orphan squash-tmp
git add -A
git commit -q -m "$msg" -m "Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>"
git branch -D main >/dev/null 2>&1 || true
git branch -m main

git push --force-with-lease="main:$expected" origin main

for b in $(git ls-remote --heads origin | awk '{print $2}' | sed 's|refs/heads/||' | grep -v '^main$'); do
  git push -q origin --delete "$b" && echo "deleted origin/$b"
done
git remote prune origin >/dev/null

for b in $(git for-each-ref --format='%(refname:short)' refs/heads | grep -v '^main$'); do
  git branch -D "$b" >/dev/null && echo "deleted local $b"
done
git worktree prune

git reflog expire --expire=now --all
git gc --prune=now -q
echo "size: $(du -sh .git | cut -f1)"

gh workflow run pages.yml
gh workflow run image.yml
