# Tools

Python 3 (standard library only). Run them from anywhere; they locate the CardScripts root
(the repository containing this folder) and the sibling repositories automatically.

| Variable | Default | Meaning |
|---|---|---|
| `EDOPRO_SCRIPTS` | repository containing this skill | CardScripts checkout |
| `EDOPRO_CDB` | every `BabelCDB*` folder next to CardScripts | extra `.cdb` files/folders (`:`-separated) |
| `EDOPRO_CORE` | `../ygopro-core` | core sources used to build the checker library |
| `EDOPRO_CACHE` | `~/.cache/edopro-card-scripting` | built `libocgcore.so`, `script_syntax_check`, `symbols.tsv` |
| `EDOPRO_CUSTOM` | `ZedjaCustomCards/` and sibling `*customcards*` repos | extra custom-card folders for the engine tests (scripts and/or `.cdb`; a `script/` subfolder is included) |
| `OCGCORE` | `$EDOPRO_CACHE/libocgcore.so` | engine library used by the engine tests |

All commands also accept `--cdb <file|folder>` (repeatable) to include a custom database.

## cdb.py

```bash
cdb.py show 101402082                 # decoded data, text, strings (Stringid map), script path
cdb.py show "Ash Blossom" --source    # name search; also print the script
cdb.py search 'banish it until the End Phase' --folder official --code 'RemoveUntil' --context 60
cdb.py search 'Raise Moon' --name --unscripted
cdb.py analogs 101402088 --top 3      # per clause, the scripted cards with the closest wording
cdb.py analogs --text 'If this card is sent to the GY: You can ...'
cdb.py archetype "Raise Moon"         # SET_ constants and how many cards match
cdb.py archetype 0x1e4
cdb.py new spec.json                  # dry run; add --db FILE --write to insert/replace
cdb.py puzzle hand:101402082 opp:mzone:89631139 -o test.lua   # EDOPro puzzle board
```

`analogs` splits the text into clauses, normalizes quoted names and numbers, and ranks
clauses of scripted cards (default folders: `official`, `pre-release`) by n-gram
similarity; when the matching script has the effect text as a comment, the line number is
shown.

## lint.py

```bash
lint.py official/c12345678.lua        # all findings
lint.py --quiet pre-release/          # errors and warnings only
lint.py --stats official/             # counts per rule
```

Codes are documented in `docs/08-testing-and-review.md`. Exit
status 1 when an error (E) is found. Uses `symbols.tsv` when available (creating it through
`loadcheck.py symbols` on first use), merged with a static index of the Lua and C++
sources; definitions from files loaded with `Duel.LoadScript("...")` are honoured.

## loadcheck.py

```bash
loadcheck.py setup [--force]          # build libocgcore.so + download ScriptChecker
loadcheck.py run FILE...              # load only these scripts (fast)
loadcheck.py run --full               # the whole repository, like CI
loadcheck.py symbols                  # dump the runtime Lua globals to symbols.tsv
```

Requires `g++` and `git`/`curl` access to GitHub for the first setup. The Lua sources come
from `ygopro-core/lua/src` when the submodule is initialised, otherwise they are fetched at
the pinned commit.

## Engine tests: explore.py, scenarios_custom.py

```bash
explore.py                                  # every scripted custom card, 16 seeds per card
explore.py --cards 270000402 --seeds 48     # selected cards
explore.py --block 2700004 --out build.json # one archetype block (passcode // 100)
explore.py --report build.json              # report of a saved run
scenarios_custom.py                         # all scripted scenario tests
scenarios_custom.py kiryu_counts_as_two_link_materials
```

Both play real duels in ygopro-core (the engine EDOPro embeds) through `duelsim.py`, which
needs the `libocgcore.so` built by `loadcheck.py setup`. `explore.py` plays seeded random
duels around each card (each in its own process) and reports Lua errors, invalid prompts,
loops and crashes, rule violations found by `duelcheck.py` (usage limits, summon locks),
prompt strings missing from the database and activated effects that no duel reached; the
exit status is 1 when it finds a problem. `scenarios_custom.py` holds scripted tests built
on `scenario.py` (steps: `Act`, `Summon`, `Pick`, `Answer`, `Option`, `Phase`, `Attack`;
probes: `lua_bool`, `lua_val`, `Duel.state()`, `Duel.codes()`); the exit status is 1 when a
test fails. The approach and what to test are described in `docs/08-testing-and-review.md`
§2b.

| File | Contents |
|---|---|
| `duelsim.py` | ctypes binding of the core API, card/script readers, prompt decoding and response encoding, policies (`Policy`, `RandomPolicy`), `Duel` |
| `duelcheck.py` | Lua observer registered inside the duel; checks of usage limits and of the custom cards' summon/activation locks (`RESOLVE_LOCKS`, `ACTIVATE_LOCKS`) |
| `explore.py` | exploration runner and report; `PROJECT_SUPPORT` lists official cards added to a custom card's deck |
| `scenario.py` | scripted-test framework |
| `scenarios_custom.py` | the tests of the ZedjaCustomCards cards |

## build_handbook.py

```bash
pip install markdown                       # only dependency outside the standard library
build_handbook.py -o handbook.html         # all docs/*.md as one self-contained web page
```

The published page is https://claude.ai/artifact/TUiK7oewrxPpppKJGih15C (private to its
owner); republish it after regenerating when the docs change.

## build_cookbook.py

```bash
build_cookbook.py            # regenerate docs/04-cookbook.md
build_cookbook.py --check    # and load + lint every template
```
