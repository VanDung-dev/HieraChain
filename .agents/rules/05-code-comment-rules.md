# Code Comment Rules

## 1. No Unsolicited Comments
* **No Proactive Commenting**: Do **NOT** add comments to code unless the user explicitly requests them (e.g. "add comments", "document this function", "thêm comment").
* **No Explanatory Annotation**: Do not insert inline `#` comments, docstrings, block headers, or section dividers as part of an unrelated change — even when the code seems non-obvious.
* **No Narrative Comments**: Do not describe what the code does line-by-line, restate the function name, or annotate self-evident logic.

## 2. When Comments Are Requested
* **Purpose Over Mechanics**: Explain *why* (rationale, trade-offs, invariants, external constraints), not *what* the statements do.
* **Keep It Accurate**: Comments must match the implementation at the time of writing; never leave stale or speculative comments.
* **Respect Terminology Rules**: Comments are subject to [01-forbidden-terms.md](01-forbidden-terms.md) — never introduce cryptocurrency terms into comments.

## 3. Preserving Existing Comments
* **Do Not Delete Unrelated Comments**: When editing code, leave existing comments in place unless they are directly invalidated by the change.
* **Update What You Invalidate**: If a change makes a nearby comment wrong, fix or remove that comment rather than leaving it misleading.

## 4. Exceptions
* **Existing Project Style Wins**: In files where a comment convention is already established (module headers, license blocks), match the surrounding style instead of stripping it out.
* **Docstrings Are Code Contracts**: Type hints remain mandatory; docstrings are only added when requested or when the file's established convention requires them.
* **Required Markers**: Tooling markers (`# noqa`, `# type: ignore`, `# pragma: no cover`) are permitted when functionally required.
