"""
md2pandoc.py  <source.md>  [output.md]
Transform IRS-PM1-Proposal-Presentation.md into a pandoc-friendly format:
  - YAML front matter for the title slide
  - ## headings without "Slide N — " prefix
  - Speaker notes converted to ::: notes … ::: divs
  - Redundant --- separators removed (headings already split slides)
"""
import re, sys, os

def transform(src: str) -> str:
    lines = src.splitlines()
    out   = []
    i     = 0

    # ── 1. Document header block (before first ---) → YAML front matter ──
    header_lines = []
    while i < len(lines) and lines[i].strip() != "---":
        header_lines.append(lines[i])
        i += 1
    i += 1   # skip the ---

    # Extract title / subtitle / author / date from header
    title    = ""
    subtitle = ""
    author   = ""
    date_str = ""
    for ln in header_lines:
        if ln.startswith("# "):
            title = ln[2:].strip()
        elif ln.startswith("## "):
            subtitle = ln[3:].strip()
        elif ln.startswith("**"):
            author = re.sub(r"\*\*([^*]+)\*\*", r"\1", ln).strip()
        elif re.match(r"\d{1,2}[–-]", ln.strip()):
            date_str = ln.strip()

    out.append("---")
    out.append(f'title: "{title}"')
    out.append(f'subtitle: "{subtitle}"')
    out.append(f'author: "{author}"')
    out.append(f'date: "{date_str}"')
    out.append("---")
    out.append("")

    # ── 2. Process slide sections ─────────────────────────────────────────
    while i < len(lines):
        line = lines[i]

        # Skip bare --- separators (headings already create slides)
        if line.strip() == "---":
            i += 1
            continue

        # ## Slide 1 — Title  →  skip (YAML front matter is the title slide)
        if re.match(r"^#{1,2}\s+Slide\s+1\s+[—–-]", line):
            # skip until next --- or next ## Slide
            i += 1
            while i < len(lines):
                if lines[i].strip() == "---" or re.match(r"^#{1,2}\s+Slide\s+", lines[i]):
                    break
                i += 1
            continue

        # ## Slide N — Title  →  ## Title
        m = re.match(r"^(#{1,2})\s+Slide\s+\d+\s+[—–-]+\s+(.+)$", line)
        if m:
            out.append(f"{m.group(1)} {m.group(2)}")
            i += 1
            continue

        # ## Appendix: …  (keep as-is, strip leading ##)
        if re.match(r"^## Appendix", line):
            out.append(line)
            i += 1
            continue

        # > **Speaker note:** …  (+ any continuation > lines)
        if re.match(r"^>\s*\*\*Speaker note:", line):
            note_text = re.sub(r"^>\s*\*\*Speaker note:\*\*\s*", "", line).strip()
            i += 1
            while i < len(lines) and lines[i].startswith(">"):
                note_text += " " + lines[i][1:].strip()
                i += 1
            out.append("")
            out.append("::: notes")
            out.append(note_text)
            out.append(":::")
            out.append("")
            continue

        # Strip "> " blockquote prefix (non-speaker-note callouts)
        if line.startswith("> "):
            out.append(line[2:])
            i += 1
            continue

        out.append(line)
        i += 1

    return "\n".join(out)


if __name__ == "__main__":
    src_path = sys.argv[1] if len(sys.argv) > 1 else "IRS-PM1-Proposal-Presentation.md"
    dst_path = sys.argv[2] if len(sys.argv) > 2 else \
        os.path.splitext(src_path)[0] + "-pandoc.md"

    with open(src_path, encoding="utf-8") as f:
        src = f.read()

    result = transform(src)

    with open(dst_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"Written: {dst_path}")
