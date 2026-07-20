# Air — Roundcube Webmail skin

A skin for [Roundcube Webmail](https://roundcube.net/) styled after macOS
**Apple Mail**. **Air** is a full, standalone rework of Roundcube's stock
*Elastic* skin: Elastic was cloned wholesale (templates, LESS sources, images,
fonts, `ui.js`) and reworked in place — not layered on with `extends` — so it
has complete control over markup, LESS variables and structure, and no runtime
dependency on Elastic.

| Skin | Folder | Notes |
|------|--------|-------|
| **Air** | `skins/air` | The primary skin. Apple system blue, frosted rail, rounded controls, light + dark mode. |
| **Air Blue** | `skins/airblue` | Thin variant that `extends: air`; contrasting blue selection only. |

## Build

Styles are **LESS compiled to committed CSS** (`styles/styles.css`,
`print.css`, `embed.css`). A fresh checkout renders without a build step;
rebuild only after editing the LESS sources. From a skin folder:

```sh
make css        # compile styles.less / print.less / embed.less via npx lessc
make css-min    # same, minified
```

Edit `.less`, never the compiled `.css`; recompile and commit the regenerated CSS.

### LESS entry points (`skins/air/styles/`)

- `colors.less` — palette (Apple system blue `#007aff` / `#0a84ff` dark)
- `mixins.less` — `.font-family` (Apple system font stack)
- `variables.less` / `_variables.less` — dimensions (`_variables.less` is the override seam)
- `_styles.less` — extra Apple rules (frost/blur, radii), imported last
- `dark.less` — dark mode (`html.dark-mode`)

## Local test harness

`docker-compose.yml` brings up Roundcube plus a throwaway GreenMail IMAP/SMTP
server, with the skins mounted live (read-only) so edits show on refresh:

```sh
docker compose up -d
# open http://localhost:8095   (login: demo@localhost / anything)
python3 tools/seed-demo.py     # 132 inbox messages + 30 work folders (idempotent)
```

Other seed helpers: `tools/seed-mail.py`, `tools/seed-mail-extra.py`, `tools/make-folders.py`.

See **[TESTING.md](TESTING.md)** for the full bring-up procedure and how to
reproduce the environment (and re-seed the demo data) after a PC restart.

## Installation

1. Copy `skins/air` into your `roundcubemail/skins/` directory.
2. In `config/config.inc.php`:

   ```php
   $config['skin'] = 'air';
   $config['skins_allowed'] = ['elastic', 'air', 'airblue'];
   ```

3. Reload (clear the browser cache if needed).

Bootstrap 4, FontAwesome 5 and `less.min.js` are bundled in each skin's `deps/`,
so no separate `bin/install-jsdeps.sh` step is needed.

## License

Licensed under the [GNU General Public License v3](LICENSE) (`GPL-3.0`), the same
license as Roundcube Webmail, from whose Elastic skin this is derived.
Bundles Bootstrap 4 (twbs/bootstrap) and FontAwesome 5 fonts under their own licenses.
