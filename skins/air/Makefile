# Apple Mail skin — build the LESS sources into the CSS files the templates load.
#
# Requires the `less` compiler (npx lessc / lessc 4.x). From the Roundcube root
# these styles also need Bootstrap in /deps (see bin/install-jsdeps.sh).
#
# Customisation entry points:
#   styles/colors.less      — palette (Apple system blue, semantic colours)
#   styles/mixins.less      — .font-family (Apple system font stack)
#   styles/_variables.less  — optional dimension overrides (seam)
#   styles/_styles.less     — extra Apple rules, imported last (frost, radii…)

css:
	npx lessc styles/styles.less styles/styles.css
	npx lessc styles/print.less  styles/print.css
	npx lessc styles/embed.less  styles/embed.css

css-min:
	npx lessc --clean-css="--s1 --advanced" styles/styles.less > styles/styles.css
	npx lessc --clean-css="--s1 --advanced" styles/print.less  > styles/print.css
	npx lessc --clean-css="--s1 --advanced" styles/embed.less  > styles/embed.css
