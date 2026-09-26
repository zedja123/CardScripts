# 08 · Testing and review

A script is "done" only after it passes every rung of this ladder. The first three are
automatic; the fourth needs the EDOPro client.

| Rung | Tool | Catches | Time |
|---|---|---|---|
| 1. Static lint | `tools/lint.py <files>` | Unknown functions/constants anywhere in the file (also inside operations), undefined `s.` functions (including the silent `SetOperation(nil)` case), empty database strings, count-limit wording mismatches, missing `chkc`, style | ~1 s |
| 2. Load test | `tools/loadcheck.py run <files>` | Syntax errors, runtime errors in `initial_effect`, wrong parameter types in `Set*` calls | ~1 s (first run builds the core, ~30 s) |
| 3. CI | GitHub Actions `check-scripts.yml` on the pull request | Same as rung 2, on the whole repository | minutes |
| 4. In-client test | `tools/cdb.py puzzle ...` + EDOPro | Behaviour: legality, resolution, rulings, interactions | manual |

---

## 1. Static lint (`lint.py`)

```bash
python3 .claude/skills/edopro-card-scripting/tools/lint.py official/c12345678.lua
python3 .claude/skills/edopro-card-scripting/tools/lint.py --quiet pre-release/   # E and W only
```

| Code | Level | Meaning |
|---|---|---|
| E001/E002/E003 | error | Missing `GetID()` / `initial_effect`, bad file name |
| E010 | error | Unknown `Namespace.Function` (checked against the runtime symbol dump) |
| E011 | error | Unknown UPPER_CASE constant |
| E012 | error | `s.name` used but never defined (a typo in `SetOperation(s.x)` or `SetValue(s.x)` is otherwise silent) |
| E030 | error | `aux.Stringid` index above 15 |
| W020 | warning | `:Method()` that exists on no object |
| W021 | warning | Deprecated or deleted function |
| W030 | warning | `aux.Stringid(id,n)` but `str(n+1)` is empty in the database |
| W041 | warning | Count limit inconsistent with the text ("each effect", "activate 1", "once per Duel", `SetSPSummonOnce`, `SetUniqueOnField`) |
| W043/W044 | warning | Targets selected without `EFFECT_FLAG_CARD_TARGET` / without `chkc` handling |
| W051 | warning | Metadata name that looks like a typo (`s.listes_names`) |
| W080 | warning | `io`, `os`, `print`, ... (unavailable in the client) |
| S0xx | style | Description missing, `+`/`\|` misuse, `GetCount`, hardcoded setcodes, header, whitespace |
| I0xx | info | Worth a look: unused strings, `listed_names`, Damage Step flag on SINGLE triggers, `if tc and` |

Exit status is 1 when any error is found.

## 2. Load test (`loadcheck.py`)

```bash
python3 .claude/skills/edopro-card-scripting/tools/loadcheck.py setup        # once per machine/session
python3 .claude/skills/edopro-card-scripting/tools/loadcheck.py run official/c12345678.lua
python3 .claude/skills/edopro-card-scripting/tools/loadcheck.py run --full   # whole repository
python3 .claude/skills/edopro-card-scripting/tools/loadcheck.py symbols      # refresh the symbol dump
```

`setup` compiles `libocgcore.so` from the local `ygopro-core` checkout (fetching the pinned
Lua sources if the submodule is absent) and downloads the same `ScriptChecker` binary the CI
uses. The cache lives in `~/.cache/edopro-card-scripting` (override with `EDOPRO_CACHE`).
Rebuild with `setup --force` after the core changes, then run `symbols` again.

## 3. In-client testing

Generate a board and load it as a puzzle:

```bash
python3 .claude/skills/edopro-card-scripting/tools/cdb.py puzzle \
    hand:101402082 deck:101402082 grave:101402082 \
    opp:mzone:89631139 opp:szone:44095762 --title "Tigress test" -o tigress-test.lua
```

Zones: `hand deck extra grave banished mzone szone fzone pzone`, prefixed with `opp:` for
the opponent. Copy the file to the EDOPro `puzzles` folder and open it from the Puzzle menu
(add `--puzzle-rules` to get the normal puzzle "win this turn" rule). Custom cards must be
installed first (`expansions/` or a configured repository).

### Scenarios to run for every effect

1. **Legality**: with no valid card to search/target/summon, the effect must not be
   offered. With a full Monster Zone, summon effects must not be offered (unless the cost
   frees a zone).
2. **Happy path**: activate, pay the cost, resolve; check the log and the result.
3. **Once-per-turn**: a second activation in the same turn (same copy and a second copy)
   is refused exactly as the text says; separate "each effect" counters do not block each
   other.
4. **Relation**: remove the target (or this card) in response; the resolution must do
   nothing (or only the independent parts, per "also").
5. **Negation**: negate the activation; OATH counts come back, "the turn you activate"
   locks disappear.
6. **Timing**: "When ..." triggers miss the timing when the event was not last; "If ..."
   triggers do not. Damage Step behaviour matches the text.
7. **Choices**: every branch of "activate/apply 1 of these effects" and every Yes/No.
8. **Hand-trap / category checks**: cards like *Ash Blossom* react only when the
   categories and operation info say so.
9. **Special statuses**: face-down, control switched, effects negated, Necrovalley for GY
   selections.

## 4. Review checklist (before committing)

**Text and data**

- [ ] Script folder and `c<passcode>.lua` name are correct.
- [ ] Header: Japanese name (or `--JP name`), exact English database name, credit line if used.
- [ ] Database entry exists with the exact text; `str1..` match the `aux.Stringid` indices.
- [ ] Effect table (02 §1) written; every sentence of the text is implemented or explicitly
      identified as handled by the database or the core.

**Structure**

- [ ] Every activated effect has a description (except bare Continuous/Field/Equip/Pendulum activations).
- [ ] Each effect is preceded by the verbatim effect-text comment.
- [ ] `SetType` / `SetCode` / `SetRange` match the effect kind; triggers: `DELAY` for "If", none for "When" and mandatory.
- [ ] Count limits follow the text exactly (02 §5).
- [ ] Costs are in `SetCost`, targets in `SetTarget` with `EFFECT_FLAG_CARD_TARGET` and a `chkc` line.
- [ ] `chk==0` checks everything the resolution needs (cards exist, zones, can draw, ...).
- [ ] Categories and `SetOperationInfo` / `SetPossibleOperationInfo` describe the effect.
- [ ] Resolution re-checks relations (`IsRelateToEffect`) and face-up status where needed.
- [ ] Connectives implemented correctly (and if you do / then / also).
- [ ] Hints before every selection; `ConfirmCards` after searches; `HintSelection` for non-targeted field selections.
- [ ] Lingering effects have the right reset and a client hint.
- [ ] Metadata: `listed_names`, `listed_series`, `material_setcode`, counters.

**Style**

- [ ] `SET_`/`CARD_`/`COUNTER_` constants, no magic numbers.
- [ ] `+` for effect types/categories/flags, `|` for everything else.
- [ ] Tabs, LF, UTF-8, no trailing whitespace.

**Verification**

- [ ] `lint.py` has no E/W findings (or each remaining one is justified in the summary).
- [ ] `loadcheck.py run` prints OK.
- [ ] In-client scenarios run by the user, or listed for them in the summary.

## 5. Upstream issues found while validating the linter (2026-09-26)

These exist in `ProjectIgnis/CardScripts` master (mirrored in this fork). They only trigger
at runtime in specific situations, which is why the CI checker does not report them.
Project Ignis asks for bug reports on Discord rather than GitHub.

| Script | Problem |
|---|---|
| `official/c60921537.lua:26` | `Group.NewGroup()` does not exist (should be `Group.CreateGroup()`); errors when "Spirit Elimination" applies |
| `official/c11224103.lua:36`, `c48229808.lua:28`, `c75830094.lua:34` | `SET_HORUS_BLACK_FLAME_DRAGON` is undefined (constant is `SET_HORUS_THE_BLACK_FLAME_DRAGON`) |
| `official/c82255872.lua:58` | `RACE_BEAST_WARRIOR` is undefined (`RACE_BEASTWARRIOR`) |
| `official/c21364070.lua:133`, `c28115467.lua:51`, `c76075139.lua:124` | `:IsController()` (typo of `:IsControler()`) |
| `official/c58981727.lua:76` | `:IsOnFiel()` (typo of `:IsOnField()`) |
| `official/c7443908.lua:65` | `:IsRACE()` (typo of `:IsRace()`) |
| `official/c11747708.lua:19` | `:IsInMainZone()` does not exist (`:IsInMainMZone()`) |
| `official/c13247801.lua:69` and ~30 others | `s.filter` (or similar) referenced but never defined (`lint.py --quiet official/` lists them) |
| `official/c11161666.lua:84` | target function uses `chkc` without declaring the parameter |
| 14 scripts | misspelled metadata names (`s.listes_names`, `s.listed_seris`, ...) |

## 6. Commit and pull-request conventions

* Upstream titles: `Add "Card Name"` (new unofficial card), `Fix "Card Name"` or
  `"Card Name" fix` / `Update "Card Name"` (fixes), `Added new card scripts` (batches).
* Upstream wants one card per pull request for unofficial additions, a Yugipedia link in
  the description, and the database entry submitted to BabelCDB (Larry's fork for
  unofficial cards). For the user's fork, follow the user's preference.
* Never commit generated caches, puzzle files or local databases unless asked.
