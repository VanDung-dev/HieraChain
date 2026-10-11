# Domain Docs

How the engineering skills should consume HieraChain's domain documentation when exploring the codebase.

## Before exploring, read these

- `GLOSSARY.md` at the repo root, when present.
- ADRs in `docs/adr/` that touch the area being explored, when present.
- Applicable rules in `.agents/rules/`, including terminology and architecture rules.

If the glossary or ADRs do not exist, proceed silently. Do not flag their absence or suggest creating them upfront. The `/domain-modeling` skill creates them lazily when terms or decisions get resolved.

## File structure

Use a single-context layout:

- `GLOSSARY.md` at the repo root.
- `docs/adr/` for architectural decision records.
- `hierachain/` for the Python package and authoritative runtime behavior.

## Use the glossary's vocabulary

When naming a domain concept in an issue title, refactor proposal, hypothesis, or test name, use the term defined in `GLOSSARY.md`. Avoid synonyms the glossary explicitly excludes, and follow `.agents/rules/01-forbidden-terms.md`.

If a needed concept is absent from the glossary, reconsider whether the project uses it or note a real gap for `/domain-modeling`.

## Flag ADR conflicts

Surface any conflict with an existing ADR explicitly instead of silently overriding the decision. Identify the ADR and explain why it may need reconsideration.
