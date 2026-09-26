# EDOPro card-scripting workflow

A reference and a repeatable procedure for scripting Yu-Gi-Oh! cards for EDOPro (Project
Ignis) in Lua, built from an analysis of the CardScripts, BabelCDB, ygopro-core and
scrapiyard repositories, the CardScripts wiki, and the PSCT card-text rules.

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

## First-time decisions (to settle once)

These are not defined by the repositories, so they need your answer the first time they
matter:

| Decision | Default until you decide |
|---|---|
| Credit line in new scripts (`--scripted by ...`) | Omitted |
| Folder for custom cards in this fork | Ask before creating one (suggestion: `custom/`) |
| Database file for custom cards | Ask (suggestion: a separate `cards-custom.cdb`, **not** on BabelCDBZedja `master`, see below) |
| Passcode block for custom cards | Ask (must avoid the reserved ranges in 06 §5) |
| One pull request per card or per batch | One per batch |
| Modernise old code around a fix | Only the touched lines |

## Important findings

* **BabelCDBZedja `master` is force-reset to upstream every hour** by its `Mirror Upstream`
  workflow (only `.github/workflows` is preserved). Do not keep custom databases there.
* The PSCT page on yugioh-card.com is blocked in this cloud environment; chapter 02 was
  verified against the card corpus instead. Allowing that host in the environment's network
  settings would let future sessions consult it directly.
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

See `tools/README.md` next to them for details.
