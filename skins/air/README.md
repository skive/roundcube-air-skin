Roundcube Webmail Skin "Apple Mail"
===================================

A skin for Roundcube Webmail styled after macOS Apple Mail. It is a full,
standalone rework of the stock **Elastic** skin — the entire Elastic skin
(templates, LESS sources, images, fonts, ui.js) was cloned and then reworked,
rather than layered on top with `extends`. This gives complete control over
markup, LESS variables and structure.

What was reworked
-----------------

- **Palette** (`styles/colors.less`): Elastic's cyan `@color-main` (#37beff)
  → Apple system blue `#007aff` / `#0a84ff` (dark). Semantic colours set to
  Apple red/green/orange. Active list selection is a full-blue row with white
  text; the unread indicator is the Apple blue dot.
- **Typography** (`styles/mixins.less`): the `.font-family` mixin now uses the
  Apple system font stack (`-apple-system, BlinkMacSystemFont, "SF Pro Text"…`)
  instead of Roboto.
- **Task rail** (`styles/colors.less` + `_styles.less`): the signature dark
  Elastic rail becomes a light translucent frosted rail; Compose is a filled
  blue action button.
- **Frosted glass & rounding** (`styles/_styles.less`, imported last): blur /
  translucency on the task rail, folder sidebar, pane headers and search bar;
  rounded controls; a floating rounded login card on a soft gradient.
- **Dark mode**: handled by Elastic's `dark.less` (`html.dark-mode`); the Apple
  accent and dark surfaces are retuned and the light rail is overridden so it
  does not leak into dark mode.

Customisation entry points
--------------------------

- `styles/colors.less`     — all colours
- `styles/mixins.less`     — `.font-family`
- `styles/variables.less`  — dimensions (+ `_variables.less` seam)
- `styles/_styles.less`    — extra Apple rules, imported last from `styles.less`


BUILD
-----

All styles are LESS and must be compiled to the CSS files the templates load
(`styles/styles.css`, `styles/print.css`, `styles/embed.css`):

```
    make css
```

or directly with the bundled compiler:

```
    npx lessc styles/styles.less styles/styles.css
    npx lessc styles/print.less  styles/print.css
    npx lessc styles/embed.less  styles/embed.css
```

The compiled CSS is committed, so a fresh checkout works without a build step;
rebuild only after editing the LESS sources.


INSTALLATION
------------

1. Copy the `air` folder into `roundcubemail/skins/`.
2. In `config/config.inc.php`:

   ```php
   $config['skin'] = 'air';
   // optional: let users pick it in Settings → Appearance
   $config['skins_allowed'] = ['elastic', 'air'];
   ```

3. Reload (clear the browser cache if needed).

This skin is self-contained and does **not** depend on the Elastic skin at
runtime (it is a clone, not an `extends`). The front-end dependencies Elastic
normally installs separately (`deps/bootstrap.min.css`,
`deps/bootstrap.bundle.min.js`, `deps/less.min.js`) are **bundled** in this
skin's `deps/` folder, so no `bin/install-jsdeps.sh` step is required for the
skin to render — Bootstrap must be present or form controls, the message
toolbar and the task rail break.


LICENSE
-------

Derived from the Roundcube Elastic skin and subject to the same Creative
Commons Attribution-ShareAlike License. Credit to the original authors is kept
here per the license.
See http://creativecommons.org/licenses/by-sa/3.0/ for details.

This folder also contains code licensed separately:
- Bootstrap Framework 4 from https://github.com/twbs/bootstrap
- FontAwesome 5 fonts from https://fontawesome.com/
- Roboto font (bundled but unused; the skin uses the system font stack)
