# Bundlephobia Helper Details

Use this reference when running optional Bundlephobia endpoints, interpreting helper output, or explaining what a package-size check does and does not prove.

## Bundlephobia Notes

- Bundlephobia's public package endpoint is `https://bundlephobia.com/api/size?package=<name[@version]>`.
- The website may add `record=true` for recent-search tracking; keep helper/API checks read-only unless the user explicitly asks to mimic a site submission.
- The site's package.json scan resolves packages, skips many backend/dev-tool packages by default, then queries the same size endpoint.
- Bundlephobia numbers are useful for "what if I import this complete npm package?" They are not a substitute for measuring the user's actual application bundle.
- Treat build errors as package-specific signals. They can indicate missing dependency declarations, unsupported package layouts, or Bundlephobia build limitations.
- Use Bundlephobia links in summaries for packages users may want to inspect manually: `https://bundlephobia.com/package/<package>`.

## Helper Commands

- `package <pkg...>`: Query Bundlephobia for one or more npm packages. Add `--exports`, `--dependencies`, `--history`, or `--similar` for deeper evidence. Add `--record-search` only when the user explicitly wants the request submitted like a site search.
- `scan --package-json <path>`: Query dependencies from a package.json. Runtime dependencies are default; add `--include-dev` and `--include-optional` when relevant.
- `pack --repo <path>`: Run `npm pack --json --dry-run` and report packed tarball, unpacked size, file count, and largest included files.
- `artifacts <path...>`: Measure local built assets and gzip sizes without publishing.
- `audit --repo <path>`: Run package.json scan, npm pack check, and artifact inspection together.

Use `--json` for machine-readable output. Use threshold flags such as `--max-gzip-kb`, `--max-size-kb`, `--max-packed-kb`, `--max-unpacked-kb`, and `--max-artifact-gzip-kb` when the user asks for pass/fail gates.

## Interpretation

- Separate "browser transfer cost" from "npm install/publish footprint".
- If package results look high, inspect dependency contributors and whether named exports are cheaper than full-package imports.
- If local pack size is high, inspect `files`, `.npmignore`, generated artifacts, source maps, tests, docs, fixtures, and bundled dependencies.
- If artifact gzip is high, recommend real bundle analysis with the project's bundler stats, source maps, `rollup-plugin-visualizer`, `webpack-bundle-analyzer`, or framework-specific analyzers.
- Do not claim a package is small or release-ready unless the relevant live check completed.
