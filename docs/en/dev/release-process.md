---
title: "Release Process"
description: "Release preparation, versioning from hierachain/config/version.py, packaging and documentation builds."
icon: material/rocket
---

# Release Process

## Versioning

`pyproject.toml` reads `hierachain.config.version.__version__`, computed from the `VERSION` tuple in `hierachain/config/version.py`. Git tags alone do not change the packaged version; this project does not use `setuptools_scm`.

## Preparation and packaging

1. Run relevant test files separately, plus required static-analysis and live-backend CI checks.
2. Synchronize corresponding English/Vietnamese docs. Changelogs describe core library changes, not documentation-only edits.
3. Update the Python version tuple and release tags consistently.

```bash
uv build
python -m twine check dist/*
```

Publication is a separate release step. See `.github/workflows/` for the configured workflow requirements.

## Documentation

Build with Zensical, English first and Vietnamese second:

```bash
zensical build -f zensical.toml
zensical build -f zensical.vi.toml
```

`.github/workflows/docs.yml` builds both languages on matching pull requests and deploys GitHub Pages on matching pushes to `main`.
