---
name: edopro-card-scripting
description: Script Yu-Gi-Oh! cards for EDOPro (Project Ignis) in Lua. Use when the user sends a card (passcode, name or card text) to script, asks to fix or review a card script, or needs a card database (CDB) entry. Covers PSCT parsing, CardScripts house style, BabelCDB entries and verification in the real ygopro-core.
---

# EDOPro card scripting

Human-readable version and full detail: `docs/` (chapters 01–09).
This file is the operational checklist. Paths are relative to the CardScripts root; `T` is
`.claude/skills/edopro-card-scripting/tools`.

## Workspace

| Repo | Role |
|---|---|
| `CardScripts/` | Scripts (`official/`, `pre-release/`, `unofficial/`, ...), root libraries (`constant.lua`, `utility.lua`, `proc_*.lua`, `cards_specific_functions.lua`, `chain.lua`), `MODERNIZING.md` |
| `BabelCDBZedja/` (any sibling `BabelCDB*`) | Card databases; its `master` is force-reset to upstream hourly, never store custom data there |
| `ygopro-core/` | Engine sources; authority for behaviour and function parameters |
| `scrapiyard/` | YAML API docs (`api/functions/<NS>/<Name>.yml`); ~30% still under construction |

## Session setup (once per session, ~30 s)

```bash
python3 $T/loadcheck.py setup     # builds libocgcore.so from ygopro-core, fetches ScriptChecker
python3 $T/loadcheck.py symbols   # runtime API dump used by lint.py
```

If a tool fails because of the network, read the environment docs and tell the user which
host is blocked; `lint.py` still works with its static index.

## Procedure (do every step; do not skip verification)

1. **Intake.** Identify each card: `python3 $T/cdb.py show <passcode|name>`. Classify:
   A = in the database (script missing or to fix), B = official but not in the database,
   C = custom. For B/C collect name, types, attribute, race, level/rank/link (+markers),
   scales, ATK/DEF, archetypes, exact text. Ask the user only for what cannot be derived
   (and to confirm the archetype number of a new custom archetype); apply the project
   decisions below without asking again.
2. **Card data.** Record stats and strings (`aux.Stringid(id,n)` = `str(n+1)`). For C take
   the passcode from `cdb.py nextid <archetype>` (`--token` for Tokens), write a JSON spec,
   run `cdb.py new spec.json` (dry run) and then `--write` (27xxxxxxx passcodes default to
   their archetype's `ZedjaCustomCards/<Archetype>.cdb`; the first card of a new archetype
   needs `--db ZedjaCustomCards/<Archetype>.cdb`). For B ask which database file to use.
3. **Effect table.** Parse the text with `docs/02-psct-to-lua.md`.
   One row per effect: verbatim text without the final period, kind + `SetType`, event/code,
   range, condition, count limit, cost, target, resolution (with connectives), categories.
   List ambiguities; prefer the behaviour of existing scripts with identical wording; ask
   when a ruling is genuinely unclear.
4. **Analogs.** `python3 $T/cdb.py analogs <passcode>` (or `--text "..."`); read the best
   1–3 scripts per effect, preferring `pre-release/` and 2024–2026 authors. Compare with
   `docs/04-cookbook.md`. Check `Cost.*`, `aux.*` and procedure
   helpers before hand-writing code. Confirm any unfamiliar name with
   `grep -P '^Name\t' ~/.cache/edopro-card-scripting/symbols.tsv` or the sources.
5. **Write.** Folder/name per chapter 03 §1. Header (`--<JP name or "JP name">`,
   `--<exact DB name>`, optional credit), `local s,id=GetID()`,
   `function s.initial_effect(c)`; setup and procedures first; one block per effect in text
   order with the verbatim comment and `SetDescription(aux.Stringid(id,n))`; metadata;
   helpers. Complete the database strings.
6. **Verify.**
   ```bash
   python3 $T/lint.py <script>            # zero E and W, or justify each remaining one
   python3 $T/loadcheck.py run <script>   # must print OK
   python3 $T/cdb.py puzzle hand:<id> ... -o <user-visible dir>/<name>-test.lua
   ```
   Then re-read the script against the effect table and the checklist in chapter 08 §4.
7. **Deliver.** Commit on the working branch (upstream-style message, e.g.
   `Add "Card Name"`), push, open/update the PR (one PR per batch; per card only for
   follow-up review work). Report: effect
   table, decisions/assumptions, lint + load-test results, the test board, scenarios to run
   in the client, open questions.

## Project decisions (user, 2026-09-26)

* Credit line: `--scripted by Zedja` as line 3 of every new script.
* Custom cards: folder `ZedjaCustomCards/` (flat), **one database per archetype** named
  after it (`ZedjaCustomCards/Prismiant.cdb`, ...), scope Custom (`ot` 0x20). Legacy
  standalone cards keep their own database (for example `AlbazTheFallen.cdb`).
* Custom passcodes: `270000000 + 100*(archetype-1) + n` (archetype 1 = 270000000-270000099);
  Tokens from the end of the block. Use `cdb.py nextid`.
* Custom archetype setcodes: `0xE00 + (archetype-1)` (archetype 1 = `0xe00`, 2 = `0xe01`),
  declared as a file-local `local SET_NAME=0xe00`; sub-archetypes use the high nibble
  (`0x1e00`, ...).
* Pull requests: one per batch; if a card needs code review afterwards, one per card.
* Fixes: modernise only the touched lines.

## Mapping rules that are easy to get wrong

* "If ...: You can" → `EFFECT_FLAG_DELAY`; "When ...: You can" → no DELAY; mandatory
  triggers → no DELAY.
* "this effect of X once per turn" → `SetCountLimit(1,id)`; "each effect" →
  `{id,0}`, `{id,1}`...; "1 X effect per turn, and only once that turn" → same `id` on all;
  "activate 1 X per turn" → `SetCountLimit(1,id,EFFECT_COUNT_CODE_OATH)`; "Special Summon X
  once per turn this way" → OATH limit on the `EFFECT_SPSUMMON_PROC`; "Special Summon X once
  per turn." → `c:SetSPSummonOnce(id)`; "control 1 X" → `c:SetUniqueOnField(1,0,id)`.
  `SetCountLimit(1,id)` and `{id,0}` are the same counter.
* Everything before `;` happens on activation (cost in `SetCost`, targets in `SetTarget`
  with `EFFECT_FLAG_CARD_TARGET` and an `if chkc then ... end` line); after `;` in
  `SetOperation`.
* Conjunctions (PSCT Part 7, docs 02 §6): "then" → B only if A happened, after
  `Duel.BreakEffect()`; "then you can" → also `SelectYesNo`; "and if you do" → B only if A
  happened, no break; "also" → independent and simultaneous, no break; plain "and" → both
  required: check both are possible before doing either. After "A, then B" the last thing
  that happened is B, so "When ...: You can" triggers on A miss the timing. "then you can
  A, and if you do, B" → check that B is possible too before `SelectYesNo`, so A is never
  paid for nothing.
* "When this card is activated: Add ..." (no "You can") is mandatory: `chk==0` requires a
  card to add. "When this card is activated: You can add ..." → `chk==0` returns true,
  `SelectYesNo` in the operation, OPT via a flag set only when used.
* "This card is also X-Attribute" → `EFFECT_ADD_ATTRIBUTE` with `SetRange(LOCATION_MZONE)`
  only (field-only, as in every official script with this wording).
* Target references (docs 02 §10): "that target"/"the targeted" → `IsRelateToEffect` +
  the target filter again; "it"/"they" → `IsRelateToEffect` only (relations survive flips
  and control changes); "both" → do nothing unless every target still qualifies.
* Conditions before the colon are checked on activation only; do not repeat them in the
  operation unless the text adds a resolution requirement ("must remain face-up ... to
  resolve"). Pay/discard/Tribute/destroy/banish before `;` is a cost; after `;` it is not.
* Summon wording (docs 02 §11): "(from your hand)" in parentheses → `EFFECT_SPSUMMON_PROC`
  (built-in, no Chain); "Must first be Special Summoned" → `EnableReviveLimit`; "cannot be
  Special Summoned by other ways" → also `AddMustBeSpecialSummoned()`; "Cannot be Normal
  Summoned/Set" → `TYPE_SPSUMMON` in the database type (lint W042).
* "Spell/Trap Card is activated" → `re:IsHasType(EFFECT_TYPE_ACTIVATE)`; "Spell/Trap effect"
  → effect of a face-up Spell/Trap; "Card or effect" → `re:IsSpellTrapEffect()`.
* "Activate 1 of these effects;" → choose in the target function (`Duel.SelectEffect`), set
  the category per choice; "apply/choose ... " on resolution → choose in the operation.
* SINGLE optional triggers are allowed in the Damage Step by the core: add
  `not Duel.IsDamageStep()` when the text excludes it; never add `EFFECT_FLAG_DAMAGE_STEP`
  to SINGLE triggers without a ruling. Quick Effects/FIELD triggers need the flag to be
  used in the Damage Step (+ `aux.StatChangeDamageStepCondition` for stat changes).
* `SetOperation(nil)` and `SetValue(nil)` are accepted silently: a misspelled function
  name there is only caught by `lint.py` (E012).
* `chk==0` must check everything the resolution needs and have no side effects; data from
  activation reaches the resolution only via targets, `SetTargetParam/Player`, labels or
  `e:GetChainData()`.
* Resolution re-checks `IsRelateToEffect(e)` for targets and for this card; no `if tc and`
  except in mandatory effects.
* Operators: `+` for `EFFECT_TYPE_*`, `CATEGORY_*`, `EFFECT_FLAG_*`; `|` for locations,
  resets, reasons, races, attributes, types, timings, positions.
* Constants: `SET_*`, `CARD_*`, `COUNTER_*`; declare a file-local constant when missing.
* Metadata: `s.listed_names` (+`id` when the text says except its own name),
  `s.listed_series`, `s.material_setcode`, counters.
* Every activated effect has a description, except the bare activation of
  Continuous/Field/Equip/Pendulum Spells and Continuous Traps.
* Never use `io`, `os`, `require`, `dofile`, `loadfile`; never define globals; never edit
  root libraries or the core as part of a card without the user's agreement.
* Never create non-hidden folders nested two levels deep in CardScripts: the CI
  ScriptChecker can then fail to load the root libraries (`loadcheck.py run` warns).

## Reference map

| Question | Read |
|---|---|
| Which construct does this wording need? | docs 02 |
| House style, strings, metadata | docs 03 |
| A full pattern to start from | docs 04 (`templates/` holds the tested sources) |
| Function signature / constant family | docs 05, then symbols dump, `lib*.cpp`, root Lua files, scrapiyard |
| Database fields, passcodes, archetypes, new entries | docs 06 |
| Engine behaviour (activation, relations, resets, Damage Step) | docs 07 |
| Lint codes, load test, test boards, review checklist | docs 08 |

## Maintenance

* After changing `templates/`, run `python3 $T/build_cookbook.py --check`.
* After changing `docs/`, rebuild the web page with `python3 $T/build_handbook.py -o <file>`
  (needs `pip install markdown`) and republish it to
  https://claude.ai/artifact/TUiK7oewrxPpppKJGih15C (pass it as `url` from a new session).
* After updating ygopro-core, run `loadcheck.py setup --force` and `loadcheck.py symbols`.
* When the house style changes upstream, update docs 03 and the rules above together.
