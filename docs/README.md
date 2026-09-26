# EDOPro card-scripting workflow

A reference and a repeatable procedure for scripting Yu-Gi-Oh! cards for EDOPro (Project
Ignis) in Lua, built from an analysis of the CardScripts, BabelCDB, ygopro-core and
scrapiyard repositories, the CardScripts wiki, and the PSCT card-text rules.

Web version: https://claude.ai/artifact/TUiK7oewrxPpppKJGih15C (private to its owner; built
from these files with `tools/build_handbook.py`).

It has two audiences:

* **You** – to review how cards are scripted, what decisions are taken and why, and to use
  as a reference.
* **Claude** – the same material, driven by the skill at
  `.claude/skills/edopro-card-scripting/SKILL.md`, with tools that automate lookup and
  verification.

## Chapters

| # | Chapter | Read it for |
|---|---|---|
| 01 | [Workflow](01-workflow.md) | The end-to-end procedure (intake → data → parse → research → write → verify → deliver) |
| 02 | [PSCT to Lua](02-psct-to-lua.md) | How each part of the card text maps to script constructs, with corpus evidence |
| 03 | [Script conventions](03-script-conventions.md) | House style: files, header, structure, naming, strings, operators, metadata |
| 04 | [Pattern cookbook](04-cookbook.md) | 32 complete, tested templates (triggers, quick effects, Spells/Traps, Extra Deck, rituals, locks, ...) |
| 05 | [API quick reference](05-api-reference.md) | The functions and constants used by almost every script, and how to look up the rest |
| 06 | [Card databases](06-card-database.md) | CDB schema, field encodings, archetypes, passcodes, creating entries |
| 07 | [Engine notes](07-engine-notes.md) | How ygopro-core loads and runs scripts: activation sequence, relations, count limits, resets |
| 08 | [Testing and review](08-testing-and-review.md) | Linter, load test, in-client test boards, review checklist, upstream bugs found |
| 09 | [Sources](09-sources.md) | What was analysed, reliability ranking, known gaps |

## How to send cards

Any of these is enough:

* a passcode or exact card name that exists in BabelCDB (for example `101402082` or
  `Tigress in Silent Repose`);
* for a card that is not in the databases: name, card type and sub-types, attribute,
  Type/race, Level/Rank/Link (+ markers), scales, ATK/DEF, archetype(s), and the exact card
  text.

Optionally add: which folder/database it belongs to, rulings you want followed, and whether
it should be committed or only reviewed.

## What you get back

1. The script, in the right folder, following the house style.
2. Database strings (and the database row for new/custom cards) when needed.
3. A short report: the effect table, decisions/assumptions, verification results (lint and
   load test), a test board (`*.lua` puzzle) and the scenarios to try in the client.

## Project decisions (settled 2026-09-26)

| Decision | Value |
|---|---|
| Credit line in new scripts | `--scripted by Zedja` (line 3 of the header) |
| Folder for custom cards | `ZedjaCustomCards/` in CardScripts (flat, no subfolders) |
| Databases for custom cards | One per archetype, named after it: `ZedjaCustomCards/<Archetype>.cdb` (next to the scripts, so the hourly BabelCDBZedja reset cannot erase them; changed from a single `ZedjaCustomCards.cdb` on 2026-09-26) |
| Passcodes for custom cards | `270000000 + 100 × (archetype − 1) + n`: archetype 1 = `270000000`–`270000099`, archetype 2 = `270000100`–`270000199`, ... (`cdb.py nextid <archetype>`) |
| Tokens of custom cards | From the end of the archetype's block downwards (`...99`, `...98`, ...), so card numbers stay contiguous |
| Setcodes of custom archetypes | `0xE00 + (archetype − 1)`: archetype 1 = `0xe00`, archetype 2 = `0xe01`, ... (the `0xB00`–`0xF00` blocks are unused by every card in BabelCDB). Each script declares it as a file-local constant (`local SET_NAME=0xe00`); add `!setname 0xe00 <Name>` to `strings.conf` to show the name in the client |
| Pull requests | One per batch; if a card needs code review, one per card afterwards |
| Modernising old code around a fix | Only the touched lines |

All of the above were confirmed by the user on 2026-09-26.

## Important findings

* **BabelCDBZedja `master` is force-reset to upstream every hour** by its `Mirror Upstream`
  workflow (only `.github/workflows` is preserved). Do not keep custom databases there.
* Chapter 02 follows Konami's PSCT articles (Parts 2–7), read from saved copies because
  yugioh-card.com is blocked in this cloud environment, and every mapping is checked against
  the official scripts. Allowing that host in the environment's network settings would let
  future sessions read the pages directly.
* The CI ScriptChecker can fail when the repository contains a non-hidden folder nested two
  levels deep with files in it; this documentation therefore lives flat in `docs/`, and any
  new folder (e.g. for custom cards) must stay one level deep.
* The linter found latent bugs in upstream official scripts (misspelled methods and
  constants, undefined functions); see 08 §5.

## Tools (summary)

All tools are Python 3 standard library, in `.claude/skills/edopro-card-scripting/tools/`:

| Tool | Purpose |
|---|---|
| `cdb.py show / search / analogs / archetype / new / puzzle` | Card lookup, text search, similar-card finder, setcodes, new database rows, test boards |
| `lint.py` | Static checks against the runtime API, the database entry and house style |
| `loadcheck.py setup / run / symbols` | Builds the core, runs the CI ScriptChecker locally, dumps the runtime API |
| `build_cookbook.py [--check]` | Regenerates chapter 04 from the templates and re-tests them |
| `build_handbook.py -o FILE` | Renders all chapters into the single web page (needs `pip install markdown`) |

See `tools/README.md` next to them for details.
