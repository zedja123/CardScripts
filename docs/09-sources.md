# 09 · Sources and reliability

## Sources analysed (snapshot 2026-09-26)

| Source | Location | Snapshot | Used for |
|---|---|---|---|
| CardScripts (fork of ProjectIgnis/CardScripts) | `zedja123/CardScripts` | `52503204` | 13,541 official + 125 pre-release scripts, root libraries, `MODERNIZING.md`, `CONTRIBUTING.md`, CI configuration |
| BabelCDB (fork of ProjectIgnis/BabelCDB) | `zedja123/BabelCDBZedja` | `80600c2` | Card databases, passcode policy, CI scripts |
| ygopro-core (fork of edo9300/ygopro-core) | `zedja123/ygopro-core` | `0764db0` | Script loading, activation/resolution, count limits, bindings; built locally for the load test |
| scrapiyard | `zedja123/scrapiyard` | `e3cf936` | YAML API documentation (functions, constants, enums) |
| CardScripts wiki | `github.com/ProjectIgnis/CardScripts.wiki.git` | `9dfd784` (2026-02-22) | Tutorials (script anatomy, filters, archetypes, counters, custom-card setup) and API tables |
| scrapi-book | `github.com/ProjectIgnis/scrapi-book` | default branch | Successor of the wiki; most pages are still TODO stubs |
| ScriptChecker | `ProjectIgnis/ScriptChecker` latest release | – | The CI load checker, run locally by `loadcheck.py` |
| PSCT articles, Parts 2–7 | yugioh-card.com (Kevin Tewart, 2011–2012), read from saved copies supplied by the user; the site is blocked by this environment's network policy | 2011-05-23 to 2012-12-12 | Chapter 02: text structure, costs, target references, Special Summon wording, terminology, conjunctions |

## Reliability ranking

When sources disagree, trust them in this order:

1. **ygopro-core C++ and the CardScripts root Lua files** – they *are* the behaviour.
2. **The runtime symbol dump** (`loadcheck.py symbols`) – what actually exists in a duel.
3. **Recent official/pre-release scripts** (2024–2026) – current idioms and rulings.
4. **scrapiyard** entries with `status: stable` and no `under-construction` tag.
5. **CardScripts wiki** API tables (last updated 2024-06; mostly accurate, some signatures
   changed since, e.g. `Duel.IsPlayerCanSpecialSummonMonster` in 2026-05).
6. Older scripts – may use deprecated idioms (`aux.SelfBanishCost`, hex setcodes,
   `GetCount`).

## About the PSCT chapter

Chapter 02 follows the PSCT article series (Parts 2–7). Part 1, the introduction, was not
among the saved copies. For each wording, the scripts of all official cards containing it
were then scanned for the construct the chapter prescribes, and the match rate is quoted.
Part 7 settled the two points the first version marked *verify*:

* "also": the two parts are **simultaneous** and **independent** (neither needs the other);
* plain "and": the two parts are simultaneous and **both are required**; if either cannot
  be done, nothing is done. Most older "and" texts have been reprinted as "and if you do".

Where an official script behaves differently from the articles (for example "Adreus,
Keeper of Armageddon" checking face-up for "it", or "Ignition Beast Volcannon" requiring
both cards for "also"), chapter 02 names the difference and follows the articles.

The articles date from 2011–2012, so their wording is older ("Graveyard", "-Type",
"Xyz Material"). Their punctuation and conjunction rules are the ones still printed on
cards. To let future sessions read the pages directly, allow `www.yugioh-card.com` in
the cloud environment's network settings.

## Validation performed

* All 32 cookbook templates load in the real core (ScriptChecker + locally built
  `libocgcore.so`) and pass the linter.
* Every function and constant named in these documents was checked against the runtime
  symbol dump (3,905 names).
* The linter was run over all official (13,541), pre-release (125) and unofficial (5,528)
  scripts to tune false positives; remaining error-level findings on official scripts are
  genuine latent bugs (08 §5).
* W042 (added with the PSCT update) reports nothing on the 359 official scripts whose text
  says "Cannot be Normal Summoned/Set", and reports a copy whose database type lacks
  `TYPE_SPSUMMON`.
* `loadcheck.py run --full` passes on the repository including these additions. An earlier
  layout (`docs/card-scripting-workflow/`) made the checker fail to open `proc_workaround.lua`;
  the documentation was flattened into `docs/` for that reason.
