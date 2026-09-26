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
| W042 | warning | Text says "Cannot be Normal Summoned/Set" but the database `type` lacks `TYPE_SPSUMMON` (0x2000000), so the core would allow a Normal Summon |
| W043/W044 | warning | Targets selected without `EFFECT_FLAG_CARD_TARGET` / without `chkc` handling |
| W051 | warning | Metadata name that looks like a typo (`s.listes_names`) |
| W080 | warning | `io`, `os`, `print`, ... (unavailable in the client) |
| W060/W061 | warning | `ZedjaCustomCards/` script with a passcode outside 27xxxxxxx / database entry without the Custom scope |
| S072 | style | `ZedjaCustomCards/` script without the `--scripted by Zedja` credit line |
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

## 2b. Engine tests (`explore.py`, scenario tests)

The load test only runs `initial_effect`. These tools play real duels in ygopro-core, the
engine EDOPro embeds, without the client: `duelsim.py` loads the `libocgcore.so` built by
`loadcheck.py setup`, serves card data and scripts, decodes every prompt and answers it.
Custom cards are read from `ZedjaCustomCards/`, sibling `*customcards*` repositories (and
their `script/` folder) and `EDOPRO_CUSTOM`.

```bash
T=.claude/skills/edopro-card-scripting/tools
python3 $T/explore.py --cards 270000402 --seeds 48   # random duels around one card
python3 $T/explore.py --block 2700004                 # every card of an archetype block
python3 $T/explore.py                                 # every scripted custom card
python3 $T/scenarios_custom.py                        # the scripted scenario tests
```

**Random exploration** (`explore.py`) builds a board around each card's archetype (the
card starts in the hand, on the field, in the GY or banished), gives the opponent either a
passive hand or hand traps and removal, and plays about 7 turns with a seeded random policy
for both players. Each duel runs in its own process. The report lists:

| Section | Meaning |
|---|---|
| errors, invalid prompts, loops, crashes | Lua errors raised while effects ran, answers the engine rejected, the engine not reaching a prompt, a crashed or hung process |
| rule violations | from `duelcheck.py`: a "once per turn"/"once per Duel" effect used twice (negated "activate 1 per turn" activations are refunded by the engine and not counted), or a forbidden Special Summon/activation after a lock (the table of locks is in `duelcheck.py`) |
| prompt strings missing | an `aux.Stringid(id,n)` shown to the player with no `str(n+1)` in the database |
| effects never reached | activated effects that no duel used: cover them with scenario tests |

Exploration only proves that effects run cleanly and respect limits; it cannot tell whether
a rule that never appears should have appeared. **Scenario tests** (`scenario.py`, tests in
`scenarios_custom.py`) build an exact board (`Debug.AddCard` also attaches Xyz materials and
marks cards as properly summoned; `Debug.PreSummon` sets the summon type), play exact
moves and assert the result:

```python
@test
def kiryu_counts_as_two_link_materials():
	d = new_duel()
	d.lua("Debug.AddCard(270000402,0,0,LOCATION_MZONE,2,POS_FACEUP_ATTACK,true)", "setup.lua")
	d.add(270000411, 0, "extra"); filler(d, 0); filler(d, 1)
	begin(d)                                   # stop at the first idle prompt
	play(d, [Summon(270000411)])               # Act(code, idx), Pick(codes), Answer(yes), Phase("bp") ...
	expect(270000411 in d.codes(0, "mzone"), "not Link Summoned with Kiryu alone")
	return d
```

Write one for every built-in summoning procedure (allowed and forbidden case), every
continuous effect with a visible result (ATK, protection, locks), and every effect the
exploration reports as never reached. Engine errors and `duelcheck.py` violations during a
scenario fail it too.

Found this way in the custom cards (2026-09-26): "Build Rider - Kiryu" (a granted procedure
that was never available, 07 §11) and the Cinder Token (a Token without `TYPE_NORMAL`,
06 §5). Neither raises an error in lint or the load test.

What these tests cannot cover: the client itself (card images, how texts and hints are
displayed) and rulings the scripts misread; a scenario asserts the tester's reading of the
text.

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
- [ ] Connectives follow 02 §6 (Part 7): "then" = success check + `BreakEffect`; "and if you do" = success check, no break; "also" = independent; plain "and" = check both parts are possible before doing either; "then you can A, and if you do, B" = offer A only while B is possible.
- [ ] A mandatory "When this card is activated: Add ..." requires a card to add in `chk==0`; "This card is also X-Attribute" uses `SetRange(LOCATION_MZONE)` (02 §8).
- [ ] Target references follow 02 §10: "that target"/"targeted" re-checks the target filter; "it"/"they" only `IsRelateToEffect`; "both" requires every target.
- [ ] Activation conditions (before the colon) are not repeated in the operation unless the text states a resolution requirement (02 §2).
- [ ] Summon wording follows 02 §11 ("must first" vs "cannot be Special Summoned by other ways"); "Cannot be Normal Summoned/Set" has `TYPE_SPSUMMON` in the database.
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

* Project policy: **one pull request per batch** of cards; if a card needs code review
  afterwards, each such card gets its own pull request.
* Upstream titles: `Add "Card Name"` (new unofficial card), `Fix "Card Name"` or
  `"Card Name" fix` / `Update "Card Name"` (fixes), `Added new card scripts` (batches).
* Upstream wants one card per pull request for unofficial additions, a Yugipedia link in
  the description, and the database entry submitted to BabelCDB (Larry's fork for
  unofficial cards). For the user's fork, follow the user's preference.
* Never commit generated caches, puzzle files or local databases unless asked.
