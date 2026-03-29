#!/bin/bash
set -e

BASENAME="IRS-PM-2026-03-29-AIS08-GRP-11-ThePlanner"
DIR="$(cd "$(dirname "$0")" && pwd)"

pandoc "$DIR/$BASENAME.md" \
  -o "$DIR/$BASENAME.docx" \
  --filter pandoc-plot \
  --metadata plot-configuration="$DIR/pandoc-plot.yml"

python3 "$DIR/format_docx.py" "$DIR/$BASENAME.docx"

echo "Done: $DIR/$BASENAME.docx"
