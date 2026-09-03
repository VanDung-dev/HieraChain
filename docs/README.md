# HieraChain Documentation Guide

The HieraChain documentation is written in Markdown and built using [Zensical](https://zensical.org/). The documentation structure is designed to support multiple languages natively, with English (`en`) currently configured as the primary language.

Inside the `docs` directory, the documentation source code is neatly separated into language-specific folders (e.g., `docs/en/` for English, `docs/vi/` for Vietnamese).

## Prerequisites

Before testing or building the documentation locally, ensure all required dependencies are installed:

```bash
pip install -e ".[doc]"
```

## Current Configuration for English (`en`)

The `zensical.toml` file located at the root directory contains the core configuration for language-based publishing. The key settings that instruct Zensical to process the English documentation are:

* **Source Directory**: `docs_dir = "docs/en"` (specifies the path containing the Markdown files)
* **UI Language**: `language = "en"` under `[project.theme]` (sets the theme's interface language to English)

## Publishing and Testing the Documentation

Make sure to run the following commands from the **root directory of the project** (where the `zensical.toml` file is located).

### 1. Serve Locally (Live Preview)

During development, you can start a local server that automatically reloads your changes. As noted in the `docs/DEV_GUIDE.md`, use the `zensical` CLI:

```bash
zensical serve
```

Open your browser at `http://127.0.0.1:8000` to view the documentation with the current language configuration.

### 2. Build Static Files (Production)

To export the documentation as a static HTML website ready for deployment (e.g., to GitHub Pages, Vercel, Nginx), run:

```bash
zensical build
```

This will quickly generate all static assets and output them to the `site/` directory.

## Multi-Language Deployment

To support multiple languages, create a separate config file for each locale and build them to isolated directories:

* `zensical.toml` → build to `site/` (English as default)
* `zensical.vi.toml` → build to `site/vi/` (Vietnamese)

Example `zensical.vi.toml`:

```toml
[project]
site_name = "HieraChain Docs"
docs_dir = "docs/vi"
site_dir = "site/vi"

[project.theme]
language = "vi"

[[project.extra.alternate]]
name = "🇬🇧 English"
link = "/"
lang = "en"
[[project.extra.alternate]]
name = "🇻🇳 Tiếng Việt"
link = "/vi/"
lang = "vi"
```

Build each language:

```bash
zensical build -f zensical.toml          # English → docs.hierachain.org
zensical build -f zensical.vi.toml       # Vietnamese → docs.hierachain.org/vi
zensical build -f zensical.ru.toml       # Russian → docs.hierachain.org/ru
```

## Custom Domain Configuration (GitHub Pages)

If you are hosting the documentation on GitHub Pages and want to use a custom domain (e.g., `docs.hierachain.org`), configure it directly in your repository's settings:

1. Navigate to your GitHub repository.
2. Go to **Settings** > **Pages**.
3. Scroll down to the **Custom domain** section.
4. Enter your domain (e.g., `docs.hierachain.org`) and click **Save**. 
5. GitHub will perform a DNS check. Ensure to tick **Enforce HTTPS** when it becomes available.

Below is an illustration of configuring the custom domain in GitHub settings:

<p align="center">
  <img src="./Screenshot.webp" width="600" height="400"/>
</p>
