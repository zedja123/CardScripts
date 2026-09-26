# Templates

Complete, tested scripts for common patterns. They are the source of
`docs/04-cookbook.md` (regenerate with
`tools/build_cookbook.py --check`, which also loads each one in the real core and lints it).

File conventions:

* line 2 `--Template: <title>`, line 3 `--PSCT: <text implemented>`;
* `--NOTE:` lines explain the pattern and are removed from the published code;
* placeholders: `SET_ARCHETYPE` (a real `SET_` constant in actual scripts), `"Archetype"`,
  `"Template"`.

These files are not named `cPASSCODE.lua`, so the repository CI checker ignores them, and
they live under a dot-folder that the delta-sync workflow skips.
