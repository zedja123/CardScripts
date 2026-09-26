# 01 · The scripting workflow

The procedure followed for every card, from receiving the request to delivering a verified
script. Each phase lists its inputs, the commands used, and what must exist before moving
on. Commands are run from the CardScripts root; `T=.claude/skills/edopro-card-scripting/tools`.

```
0 Intake ─► 1 Card data ─► 2 Parse (effect table) ─► 3 Research analogs ─► 4 Write
                                                                             │
          6 Deliver ◄── 5 Verify (lint → load test → board for client test) ◄┘
```

---

## Phase 0 · Intake

**Input**: one or more cards from the user, as a passcode, a name, or full card text.

| Situation | Recognised by | Consequence |
|---|---|---|
| A. Card exists in BabelCDB but has no script, or its script must be fixed | `cdb.py show` finds it; `script: NOT SCRIPTED` or an existing path | Use the database text as the source of truth |
| B. Official card not in BabelCDB yet (new announcement) | Not found; user gives text/stats | Needs a prerelease-style entry and passcode |
| C. Custom card | User says so, or not found and no official source | Needs a custom entry, passcode in the custom range, custom archetype if any |

Ask the user only for what cannot be derived: missing stats or text for B/C and the intended
behaviour when the text is ambiguous. Everything else follows this guide and the project
decisions in the README: custom cards go to `ZedjaCustomCards/` with their row in their
archetype's database `ZedjaCustomCards/<Archetype>.cdb`, passcodes come from `cdb.py nextid <archetype>`,
and every new script carries `--scripted by Zedja`. For a new custom archetype, confirm its
number (and therefore its passcode block) with the user.

**Exit criterion**: every card has either a database entry or a complete spec (name, type,
stats, exact text).

## Phase 1 · Card data

```bash
python3 $T/cdb.py show <passcode|name>          # decoded stats, text, strings, script path
python3 $T/cdb.py show <passcode> --source      # plus the current script, if any
```

* Note the type, attribute, race, level/rank/link, scales, markers and archetypes: filters
  in the script depend on them.
* Read the **strings** (`aux.Stringid(id,n)` = `str(n+1)`). Official entries usually have
  them; if they are missing, plan them (06 §7).
* For B/C, write the JSON spec and create the row with `cdb.py new` (dry run first; write
  only to the database file agreed with the user).

**Exit criterion**: the exact text and all stats are known; the strings plan exists.

## Phase 2 · Parse the text (effect table)

Apply [02 · PSCT to Lua](02-psct-to-lua.md):

1. Split into material/summon lines, activated effects (colon/semicolon), continuous
   effects, procedures and the usage-limit sentence.
2. For each effect fill one row of the effect table: verbatim text (without the final
   period), kind and `SetType`, event/code, range, condition, count limit, cost, target,
   resolution steps with their connectives, categories.
3. Mark anything the database handles instead of the script ("always treated as ...",
   `TYPE_SPSUMMON` for "Cannot be Normal Summoned/Set").
4. In the resolution column, name each conjunction (then / also / and if you do / and) and
   each target reference (that target / it / both); they decide the success checks,
   `BreakEffect` calls and resolution re-checks (02 §6, §10).
5. Mark every ambiguity (rulings, unusual wording). For official cards, prefer the behaviour
   of existing scripts with the same wording; if none exists and the ruling is unclear, ask
   the user and record the decision. Where official scripts disagree with the PSCT articles,
   02 names the difference; follow the articles for new scripts.

**Exit criterion**: a complete effect table, with ambiguities either resolved or listed.

## Phase 3 · Research analogs

```bash
python3 $T/cdb.py analogs <passcode>                    # per clause: most similar scripted cards
python3 $T/cdb.py analogs --text "<text of a custom card>"
python3 $T/cdb.py search '<regex on the wording>' --folder official --code '<regex in script>'
```

* For each effect pick the best 1–3 real scripts with the **same wording**; prefer recent
  ones (pre-release folder, 2024–2026 authors such as pyrQ, Naim, Hatter) because they
  follow the current style.
* Compare them with the [cookbook](04-cookbook.md) template of the same pattern.
* Check helper functions before writing code by hand: `Cost.*`, `aux.*`, procedures
  (05 §8–9), archetype helpers in `cards_specific_functions.lua`.
* Look up any unfamiliar function in the runtime dump / source (05, "How to look anything
  else up").

**Exit criterion**: every row of the effect table has a reference implementation.

## Phase 4 · Write the script

1. Path: folder per [03 §1](03-script-conventions.md); file `c<passcode>.lua`.
2. Header, `local s,id=GetID()`, `function s.initial_effect(c)`.
3. Card-level setup and procedures first, then one block per effect in text order, each
   with its verbatim comment and `SetDescription(aux.Stringid(id,n))`.
4. Metadata (`s.listed_names`, `s.listed_series`, ...), then helper functions in use order.
5. Conventions: [03](03-script-conventions.md); engine rules to respect:
   [07](07-engine-notes.md) (chk/chkc, relations, Damage Step, resets).
6. Add or complete the database strings so every `aux.Stringid` index has text.

**Exit criterion**: the script implements every row of the effect table.

## Phase 5 · Verify

```bash
python3 $T/lint.py <script>                 # fix every E and W (or justify it)
python3 $T/loadcheck.py run <script>        # must print OK
python3 $T/cdb.py puzzle hand:<id> ... -o <name>-test.lua   # board for the in-client test
```

* Re-read the script against the effect table line by line (08 §4 checklist).
* Walk through the scenarios in 08 §3 mentally; list the ones the user should run in the
  client.

**Exit criterion**: lint clean, load test OK, checklist complete.

## Phase 6 · Deliver

1. Commit the script (and database changes) on the working branch with a message in the
   upstream style (`Add "Card Name"`, `Added new card scripts`).
2. Push and open or update the pull request: **one pull request per batch**. If a card in
   the batch needs code review afterwards, handle each such card in its own pull request.
3. Report to the user:
   * the effect table (or a condensed version),
   * decisions and assumptions (rulings, ambiguous wording),
   * verification results (lint, load test),
   * the in-client test board and the scenarios to run,
   * anything left open.

---

## Batches and archetypes

* Script the core cards first, then the support cards, so that `s.listed_names` and shared
  helpers are consistent.
* Keep each script self-contained; shared logic only goes into the root libraries when it is
  reused widely (and then it is a separate, deliberate change).
* Verify the whole batch together: `lint.py <folder or files>` and
  `loadcheck.py run <files...>`.

## Fixing an existing script

1. `cdb.py show <id> --source`; reproduce the problem from the user's description.
2. Find the corrected pattern (analogs, cookbook, engine notes).
3. Change only what the fix needs (plus modernisation of the touched lines if the user
   wants it, per MODERNIZING.md).
4. Verify as in Phase 5; describe the behaviour before and after.

## When something is not covered

* No analog and no template: build it from the engine notes (07), the effect codes in
  `constant.lua` and the corresponding core behaviour; say so explicitly in the report.
* Needs a new root helper, constant or core change: propose it separately; do not modify
  root libraries or the core as part of a card script without the user's agreement.
