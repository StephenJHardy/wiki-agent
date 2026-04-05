# Deferred Engineering Items

This document records engineering work that was investigated and intentionally deferred.

## 2026-04-05: Docling as a replacement for the current PDF/HTML ingest stack

- Status: Deferred
- Scope: Replace the current `pymupdf4llm` + `pymupdf` PDF path and `trafilatura` HTML path with `docling`

### Why it was deferred

- `docling` works in isolation on this machine and can convert both PDF and HTML to Markdown.
- It is not a clean in-process replacement for the current app dependency set.
- The active project dependency pin is `typer>=0.24.1`.
- Current `docling` metadata requires `typer>=0.12.5,<0.22.0`.
- The full dependency solve for the current app plus `docling` is unsatisfiable because of that `typer` constraint.

### What was verified

- `docling` imported successfully under Python `3.13.5`.
- `DocumentConverter` converted a sample PDF to Markdown.
- `DocumentConverter` converted a sample HTML document to Markdown and preserved LaTeX delimiters like `\\(E=mc^2\\)`.
- The direct project solve failed when combining:
  - current app dependencies
  - `trafilatura>=2.0.0`
  - `typer>=0.24.1`
  - `docling`

### Current decision

- Keep the current local-first ingest stack:
  - PDF: `pymupdf4llm`, with `pymupdf` fallback
  - HTML: raw local snapshot plus `trafilatura`
- Preserve raw local source files as the ground truth artifact.
- Treat Docling as a future optional high-fidelity parser, not the default parser today.

### Recommended revisit paths

1. Test whether the CLI and viewer still behave correctly on `typer<0.22.0`.
2. If not, add Docling as an optional sidecar extractor invoked out-of-process.
3. Revisit full replacement only if Docling relaxes its `typer` constraint or the app dependency graph changes enough to accommodate it cleanly.

### Notes

- Earlier install investigation showed a stale-looking `deepsearch-glm` issue, but the current isolated Docling install path on this machine no longer fails for that reason.
- The present blocker is dependency compatibility, not Python version support or basic Docling functionality.
