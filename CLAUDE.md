# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

A **Roundcube Webmail skin** styled after macOS **Apple Mail**. The main skin is
**Air** (`skins/air`) — a full standalone rework of Roundcube's stock *Elastic*
skin. Elastic was cloned wholesale (templates, LESS, images, fonts, `ui.js`) and
reworked in place, **not** layered with `extends`, so we have complete control
over markup, LESS variables and structure. At runtime Air does not depend on
Elastic.

## Skins in `skins/`

- **`air`** — the primary skin ("Air"). This is the source of truth. Tracked.
- **`airblue`** — "Air Blue", a thin variant that `extends: air` (see its
  `meta.json`). Only overrides colours (contrasting blue selection). Tracked.

## Build

Styles are **LESS compiled to committed CSS** (`styles/styles.css`,
`print.css`, `embed.css`). A fresh checkout works without building; rebuild only
after editing LESS sources.

From a skin folder (e.g. `skins/air`):

```
make css          # npx lessc for styles.less, print.less, embed.less
make css-min      # same, minified via clean-css
```

Always recompile after editing any `.less` and commit the regenerated `.css`.

## LESS customisation entry points (in `skins/air/styles/`)

- `colors.less`      — palette (Apple system blue `#007aff` / `#0a84ff` dark, semantic red/green/orange)
- `mixins.less`      — `.font-family` (Apple system font stack)
- `variables.less` / `_variables.less` — dimensions (`_variables.less` is the override seam)
- `_styles.less`     — extra Apple rules (frost/blur, radii); imported **last** from `styles.less`
- `dark.less`        — dark mode (`html.dark-mode`)

## Local test harness (`docker-compose.yml`)

- `roundcube` (roundcube/roundcubemail:latest) + `greenmail` throwaway IMAP/SMTP (auth disabled).
- Skins are mounted live read-only, so LESS→CSS edits show on refresh.
- Bring up: `docker compose up -d` → http://localhost:8095 (login `demo@localhost` / anything).
- Seed demo mail: `python3 tools/seed-mail.py` (also `seed-mail-extra.py`, `make-folders.py`).

## Conventions

- Commit messages are lowercase, area-prefixed, imperative — e.g.
  `folder list: 40px pill height; centre the expand arrow`.
- Keep changes scoped to `air` (and `airblue` for the blue variant) unless told otherwise.
- Match the surrounding LESS idiom; edit `.less`, never hand-edit compiled `.css`.
