# VizuAI / MONTER

VizuAI is the repository for **MONTER**, a cinematic editorial intelligence system.

MONTER does not upload giant RAW folders to the web. It separates media processing from editorial reasoning:

- `packages/bridge` — local, 8GB-RAM-first ingest/proxy engine.
- `apps/studio` — Vercel-hosted workspace for assets, director intent, edit plans and later critic/transition reasoning.
- `contracts` — portable data contracts shared between the two sides.

## Development rule

Every pull request must pass Studio and Bridge tests before it is considered merge-ready.

See `docs/ARCHITECTURE.md` and `docs/OPEN_SOURCE.md`.
