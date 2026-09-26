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
| PSCT guide | `yugioh-card.com/en/play/psct/` | **not accessible** (blocked by this environment's network policy) | Replaced by corpus verification; see below |

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

The official PSCT pages could not be fetched from the analysis environment. Chapter 02 was
written from established PSCT knowledge and then checked against the corpus: for each
wording, the scripts of all official cards containing it were scanned for the construct
the chapter prescribes, and the match rate is quoted. Two points are marked *verify*
because the corpus cannot settle them by itself:

* whether "also" parts are simultaneous with the preceding part (the scripts treat them as
  independent and unconditional, which is what matters for implementation);
* the exact behaviour of plain "and" when one part cannot be performed (ruling-dependent).

To enable direct access in future sessions, allow `www.yugioh-card.com` in the cloud
environment's network settings.

## Validation performed

* All 32 cookbook templates load in the real core (ScriptChecker + locally built
  `libocgcore.so`) and pass the linter.
* Every function and constant named in these documents was checked against the runtime
  symbol dump (3,905 names).
* The linter was run over all official (13,541), pre-release (125) and unofficial (5,528)
  scripts to tune false positives; remaining error-level findings on official scripts are
  genuine latent bugs (08 §5).
* `loadcheck.py run --full` passes on the repository including these additions. An earlier
  layout (`docs/card-scripting-workflow/`) made the checker fail to open `proc_workaround.lua`;
  the documentation was flattened into `docs/` for that reason.
