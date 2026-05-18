---
title: "Release Process"
description: "Version release and documentation process: versioning with setuptools_scm, packaging, release notes."
icon: material/rocket
---

# Release Process

## Versioning

* Uses `setuptools_scm` (see `pyproject.toml`) to infer version from Git tags.
* Create tags following the pattern: `vX.Y.Z` or `vX.Y.Z.devN` for development builds.

## Release Preparation

1. Ensure tests pass: `pytest -v`.
2. Review documentation: links/index/nav updated.
3. Update `docs/en/changelog.md` with release content.

## Packaging

```bash
python -m build
twine check dist/*
# (optional) twine upload dist/*
```

## Documentation Release

* Build static site with MkDocs (performed after content stabilizes).
* CI (later): build preview on PR, publish on merge to `main`.

## Release Notes

* Summarize main changes to code and documentation.
* Link to related PRs; list breaking changes if any.
