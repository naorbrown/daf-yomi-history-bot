#!/bin/bash
# Create a pull request for the current branch
# Requires: gh CLI (https://cli.github.com/)
#
# Usage: ./scripts/create-pr.sh "PR Title" "PR Body"
# Or just: ./scripts/create-pr.sh (uses auto-generated title/body from commits)

set -e

# Check if gh is installed
if ! command -v gh &> /dev/null; then
    echo "Error: gh CLI not installed. Install from https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "Error: Not authenticated. Run: gh auth login"
    exit 1
fi

# Get current branch
BRANCH=$(git branch --show-current)
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
    echo "Error: Cannot create PR from main/master branch"
    exit 1
fi

# Get base branch (default to main)
BASE_BRANCH="${BASE_BRANCH:-main}"

# Generate title from branch name if not provided
if [ -n "$1" ]; then
    TITLE="$1"
else
    # Convert branch name to title (e.g., fix-duplicate-video -> Fix duplicate video)
    TITLE=$(echo "$BRANCH" | sed 's/claude\///' | sed 's/-/ /g' | sed 's/\b\(.\)/\u\1/')
fi

# Generate body from commits if not provided
if [ -n "$2" ]; then
    BODY="$2"
else
    # Get commit messages since branching from base
    COMMITS=$(git log "$BASE_BRANCH".."$BRANCH" --pretty=format:"- %s" 2>/dev/null || echo "")
    BODY="## Summary

$COMMITS

## Test plan

- [ ] Verify changes work as expected

---
*Auto-generated PR*"
fi

echo "Creating PR..."
echo "  Branch: $BRANCH -> $BASE_BRANCH"
echo "  Title: $TITLE"
echo ""

gh pr create \
    --title "$TITLE" \
    --body "$BODY" \
    --base "$BASE_BRANCH" \
    --head "$BRANCH"

echo ""
echo "PR created successfully!"
