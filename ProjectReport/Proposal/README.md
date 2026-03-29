# Proposal Build

`convert.sh` converts the proposal Markdown file to PDF using pandoc.

## Dependencies

| Dependency | Purpose |
|---|---|
| `pandoc` | Converts Markdown to DOCX |
| `mermaid-filter` | Pandoc filter that renders Mermaid diagrams |

## Installation

```bash
# pandoc
sudo apt install pandoc

# mermaid-filter (requires Node.js/npm)
npm install -g mermaid-filter
```

## Usage

```bash
./convert.sh
```

Output: `IRS-PM-2026-03-29-AIS08-GRP-11-ThePlanner.docx`
