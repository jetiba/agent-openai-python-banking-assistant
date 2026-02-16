#!/usr/bin/env bash
# ===========================================================================
# setup-lab.sh — Apply lab delta files to the workspace root
#
# Usage:
#   ./setup-lab.sh <lab-number>
#
# Examples:
#   ./setup-lab.sh 2          # copies labs/lab-02 delta files into root
#   ./setup-lab.sh 3          # copies labs/lab-03 delta files into root
#
# Lab 1 is the root's initial state — nothing to copy.
# Each lab builds on the previous, so run them in order:
#   Lab 1 → (root already)
#   Lab 2 → ./setup-lab.sh 2
#   Lab 3 → ./setup-lab.sh 3
# ===========================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAB_NUM="${1:-}"

if [[ -z "$LAB_NUM" ]]; then
  echo "Usage: $0 <lab-number>"
  echo "  e.g. $0 2"
  exit 1
fi

# Zero-pad to 2 digits
LAB_DIR="$ROOT_DIR/labs/lab-$(printf '%02d' "$LAB_NUM")"

if [[ ! -d "$LAB_DIR" ]]; then
  echo "Error: Lab directory not found: $LAB_DIR"
  exit 1
fi

echo "========================================"
echo " Applying Lab $LAB_NUM delta files"
echo " Source: $LAB_DIR"
echo " Target: $ROOT_DIR"
echo "========================================"

# Copy all files from the lab directory into root, preserving directory structure.
# Skip README.md (lab instructions stay in the lab folder).
cd "$LAB_DIR"
find . -type f ! -name 'README.md' | while read -r file; do
  src="$LAB_DIR/$file"
  dest="$ROOT_DIR/$file"
  mkdir -p "$(dirname "$dest")"
  cp "$src" "$dest"
  echo "  → $file"
done

echo ""
echo "Done! Lab $LAB_NUM files applied to workspace root."
echo "You can now run 'azd up' from the root directory."
