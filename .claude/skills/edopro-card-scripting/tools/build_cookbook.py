#!/usr/bin/env python3
"""Build docs/04-cookbook.md from the templates, optionally testing them.

  build_cookbook.py            regenerate the cookbook chapter
  build_cookbook.py --check    also load every template in the real core and lint it

Each template in ../templates is a complete script. Header conventions:
  line 2  --Template: <title>
  line 3  --PSCT: <card text the template implements>
  --NOTE: <explanation>   (any number of lines, removed from the published code)
Placeholders: SET_ARCHETYPE (an archetype constant), "Archetype", "Template".
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

TEMPLATES = C.SKILL_DIR / "templates"
OUT = C.SCRIPTS_ROOT / "docs" / "04-cookbook.md"

INTRO = """# 04 · Pattern cookbook

Complete, tested scripts for the patterns that cover most cards. Every template below is
generated from `.claude/skills/edopro-card-scripting/templates/` and is verified to load in
the real core and to pass the linter (`tools/build_cookbook.py --check`).

How to use a template:

1. Find the closest template here **and** the closest real cards with
   `cdb.py analogs <card>`; prefer the real card when it matches the wording exactly.
2. Replace the placeholders: `SET_ARCHETYPE` with the real `SET_` constant, `"Archetype"`
   and `"Template"` in comments with the real names.
3. Keep the effect comment identical to the database string of that effect.

Placeholders are not real constants; the templates only load when `SET_ARCHETYPE` is
defined (the checker defines it as a test value).

## Index

"""


def parse(path: Path):
	lines = path.read_text(encoding="utf-8").split("\n")
	title = lines[1].removeprefix("--Template:").strip()
	psct = lines[2].removeprefix("--PSCT:").strip()
	notes = [ln.removeprefix("--NOTE:").strip() for ln in lines if ln.startswith("--NOTE:")]
	code = [ln for ln in lines if not ln.startswith("--NOTE:")]
	code = ["--(Japanese name)", "--Template"] + code[3:]
	return title, psct, notes, "\n".join(code).rstrip() + "\n"


def build() -> str:
	parts = [INTRO]
	items = [(p, *parse(p)) for p in sorted(TEMPLATES.glob("*.lua"))]
	for p, title, _, _, _ in items:
		anchor = p.stem.replace("_", "-")
		parts.append(f"- [{p.stem[:2]} · {title}](#{anchor})\n")
	for p, title, psct, notes, code in items:
		anchor = p.stem.replace("_", "-")
		parts.append(f"\n---\n\n<a id=\"{anchor}\"></a>\n## {p.stem[:2]} · {title}\n\n")
		parts.append(f"> {psct}\n\n")
		if notes:
			parts.append("".join(f"- {n}\n" for n in notes) + "\n")
		parts.append(f"Source: `templates/{p.name}`\n\n```lua\n{code}```\n")
	return "".join(parts)


def check() -> int:
	tools = Path(__file__).resolve().parent
	with tempfile.TemporaryDirectory(prefix="edopro-tpl-") as tmp:
		files = []
		for n, p in enumerate(sorted(TEMPLATES.glob("*.lua")), 1):
			lines = p.read_text(encoding="utf-8").split("\n")
			lines.insert(3, "SET_ARCHETYPE=0x1e4")
			f = Path(tmp) / f"c{999000000 + n * 10}.lua"
			f.write_text("\n".join(lines), encoding="utf-8")
			files.append(str(f))
		rc1 = subprocess.run([sys.executable, str(tools / "loadcheck.py"), "run", *files]).returncode
		rc2 = subprocess.run([sys.executable, str(tools / "lint.py"), "--quiet", *files]).returncode
	return rc1 or rc2


def main():
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("--check", action="store_true")
	args = ap.parse_args()
	OUT.write_text(build(), encoding="utf-8")
	print(f"wrote {OUT}")
	return check() if args.check else 0


if __name__ == "__main__":
	sys.exit(main())
