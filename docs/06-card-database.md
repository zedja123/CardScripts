# 06 · Card databases (BabelCDB)

A card needs a **database entry** (stats, text, strings) and, unless it is a non-Pendulum
Normal Monster, a **script**. The entry's passcode ties them together. This chapter covers
reading entries, what every field means, and creating entries for new or custom cards.

---

## 1. Files in BabelCDB

| File | Content (2026-09) |
|---|---|
| `cards.cdb` | 14,759 released OCG/TCG cards (`ot` 0x3 both, 0x1 OCG-only, 0x2 TCG-only) |
| `release-<set>.cdb` | Region-limited releases (e.g. `release-betb.cdb`, OCG) |
| `prerelease-<set>.cdb` | Announced cards with prerelease passcodes (`ot` includes 0x100) |
| `cards-unofficial.cdb` | Anime/manga/video-game cards (`ot` 0x4, 0x10, 0x8) |
| `cards-rush.cdb`, `prerelease-cards-rush.cdb` | Rush Duel (`ot` 0x200) |
| `cards-skills*.cdb` | Speed Duel skills (`ot` 0x40) |
| `goat-entries.cdb` | GOAT-format variants (`ot` 0x8) |

The same passcode can appear in several files (for example a card moving from pre-release
to release); `cdb.py show` lists every file that contains it.

**Fork caveat (BabelCDBZedja).** Its `Mirror Upstream` workflow runs hourly and does
`git reset --hard upstream/master` followed by a force-push, restoring only
`.github/workflows`. Anything else committed to `master` of the fork (for example a custom
database) is **erased within the hour**. Keep custom databases on another branch, in another
repository, or in the client's `expansions/` folder.

## 2. Schema

```sql
CREATE TABLE datas (id INTEGER PRIMARY KEY, ot INTEGER, alias INTEGER, setcode INTEGER,
                    type INTEGER, atk INTEGER, def INTEGER, level INTEGER, race INTEGER,
                    attribute INTEGER, category INTEGER);
CREATE TABLE texts (id INTEGER PRIMARY KEY, name TEXT, desc TEXT,
                    str1 TEXT, ..., str16 TEXT);
```

`python3 tools/cdb.py show <passcode|name>` decodes every field; the table below explains
them.

## 3. Fields

| Field | Encoding | Notes |
|---|---|---|
| `id` | Passcode | Script file `c<id>.lua` |
| `ot` (scope) | Bits: 0x1 OCG, 0x2 TCG, 0x4 Anime, 0x8 Illegal, 0x10 Video Game, 0x20 Custom, 0x40 Speed, 0x100 Pre-release, 0x200 Rush, 0x400 Legend, 0x1000 Hidden | Decides which formats list the card; custom cards use 0x20 |
| `alias` | Passcode | Within 10 of `id`: alternate artwork (same card, shares the script). Further away: the card's **name is treated as** the alias for game purposes (e.g. *A Legendary Ocean* → "Umi"); the card keeps its own script |
| `setcode` | Up to four 16-bit archetype codes packed low to high (`0x0009_3008` = "Neos" + "Elemental HERO") | Use `SET_*` constants in scripts |
| `type` | `TYPE_*` bits (`constant.lua`), e.g. Effect Monster 0x21, Tuner Effect 0x1021, Link Effect 0x4000021, Quick-Play Spell 0x10002, Continuous Trap 0x20004, Token 0x4011 | A Main Deck monster whose text says "Cannot be Normal Summoned/Set" needs `TYPE_SPSUMMON` (0x2000000), e.g. 0x2000021; the core uses this bit to refuse Normal Summons (02 §11, lint W042) |
| `atk` / `def` | Integers; `-2` = "?" | Link Monsters store **link markers** in `def` |
| `level` | Level/Rank/Link Rating in the low byte; Pendulum scales in bits 24–31 (left) and 16–23 (right) | `0x5050004` = Level 4, scales 5/5 |
| `race` | `RACE_*` bits (64-bit) | |
| `attribute` | `ATTRIBUTE_*` bits | |
| `category` | Deck-editor search filters (not the script `CATEGORY_*`) | Optional; 0 is fine for custom cards |
| `name`, `desc` | English name and card text | `desc` must be the exact PSCT text; line 2 of the script repeats `name` |
| `str1`..`str16` | Script strings | `aux.Stringid(id,n)` reads `str(n+1)` |

Link markers (value in `def`): BL 0x1, B 0x2, BR 0x4, L 0x8, R 0x20, TL 0x40, T 0x80,
TR 0x100.

## 4. Archetypes (setcodes)

* A setcode is 16 bits: the low 12 bits identify the archetype, the high 4 bits a
  sub-archetype. The core (`card::match_setcode`) requires the low 12 bits to be equal and
  the card's sub-archetype nibble to contain **every bit** of the requested one:
  `c:IsSetCard(0x8)` ("HERO") matches every `0x?008`; `c:IsSetCard(0x3008)` ("Elemental
  HERO") matches `0x3008` and `0x7008`/`0xb008`/`0xf008`, but not `0xa008` ("Masked HERO").
  Hence `IsSetCard(0x3184)` matches a `0x7184` card, while `IsSetCard(0x7184)` does not
  match a `0x3184` card.
* Constants live in `archetype_setcode_constants.lua` (615 entries). Look one up with
  `cdb.py archetype "<name>"` or `cdb.py archetype 0x1e4`.
* New archetype for a custom card: official `SET_` constants stop at `0x208` and the
  anime/manga entries at `0xac1`; the `0xB00`–`0xF00` blocks are unused. **Project rule
  (confirmed):** `0xE00 + (archetype − 1)`, so archetype 1 = `0xe00`, archetype 2 = `0xe01`
  (`cdb.py nextid <archetype>` prints it). Declare it at the top of each script as a
  file-local constant (`local SET_NAME=0xe00`), put it in the database `setcode`, and
  optionally show its name in the client with a `strings.conf` line `!setname 0xe00 <Name>`.
  A sub-archetype inside a custom archetype uses the high nibble (`0x1e00`, `0x2e00`, ...;
  see the matching rule above).

## 5. Passcodes

| Range | Reserved for |
|---|---|
| Up to 8 digits | Official cards |
| `10ZZYYXXX` / `1002YYXXX` / `1003YYXXX` / `1004YYXXX` | OCG/TCG prerelease passcodes (main sets, side sets, structure/starter decks, deck build/duelist packs) |
| `100XXXXXX` | Video-game cards |
| `160ZYYXXX` | Rush Duel |
| `30ZYYYXXX` | Speed Duel skills |
| `5XXXXXXXX`, `200XXXXXX`, `800XXXXXX`, `810XXXXXX`, `777777777` | Anime/manga |

**Custom cards (project decision):** passcodes `270000000 + 100 × (archetype − 1) + n`
(archetype 1 = `270000000`–`270000099`, archetype 2 = `270000100`–`270000199`, ...). The
27xxxxxxx range is unused in every BabelCDB database (checked 2026-09-26).
`cdb.py nextid <archetype>` prints the next free number (it checks all databases and
scripts). Upstream Tokens usually take the card's passcode + 1; inside a 100-number block that
would collide with the next card, so custom Tokens take numbers from the **end** of the block
(`cdb.py nextid <archetype> --token`). Each Token needs its own database entry (type
`TYPES_TOKEN`).

## 5b. Choosing the database file

| Card | Database |
|---|---|
| Unscripted official card already in BabelCDB | None to create; only the strings may need completing |
| New prerelease card | `prerelease-<set>.cdb` (upstream practice) |
| Custom card | The database of its archetype, `ZedjaCustomCards/<Archetype>.cdb` (project decision: one database per archetype). `cdb.py new --write` picks it by default: the `.cdb` in `ZedjaCustomCards/` that holds the other cards of the same passcode block. The first card of a new archetype needs `--db ZedjaCustomCards/<Archetype>.cdb`, which creates the file |

## 6. Creating or updating an entry

`cdb.py new` builds the row from a readable JSON spec and writes it only with `--write`:

```json
{
  "id": 270000000,
  "name": "Example Custom Monster",
  "ot": "custom",
  "type": ["monster", "effect", "tuner"],
  "race": "machine",
  "attribute": "earth",
  "level": 3,
  "atk": 500,
  "def": 500,
  "setcodes": ["0xe00"],
  "desc": "If this card is Normal Summoned: You can add 1 \"Example\" card from your Deck to your hand. ...",
  "strings": ["If this card is Normal Summoned: You can add 1 \"Example\" card from your Deck to your hand"]
}
```

* `type` accepts `TYPE_` names without the prefix (`"monster|effect|link"` also works);
  `race`/`attribute` likewise; `ot` accepts scope names or a number.
* Xyz: `"rank": 4`; Link: `"link": 2, "link_markers": ["bottom-left","bottom-right"]`;
  Pendulum: `"lscale": 5, "rscale": 5` (or `"scale"`); "?" stats: `"atk": "?"`.
* `setcodes` accepts `SET_` constant names or hex strings, up to four.

```bash
python3 tools/cdb.py nextid 1                            # next free passcode of custom archetype 1
python3 tools/cdb.py new card.json                       # dry run: prints the row and the target file
python3 tools/cdb.py new card.json --write               # 27xxxxxxx -> its archetype's ZedjaCustomCards/<Archetype>.cdb
python3 tools/cdb.py new card.json --db ZedjaCustomCards/Milacresy.cdb --write   # first card of a new archetype
python3 tools/cdb.py new card.json --db other.cdb --write   # any other database, explicitly
python3 tools/cdb.py show 270000000                      # the custom database is always included
```

GUI alternatives: DataEditorX (use the Project Ignis `cardinfo_english.txt` for the EDOPro
categories and scopes) or Datacorn.

## 7. Strings checklist

1. One string per activated effect, in text order, text = effect text without the final
   period.
2. Then the extra strings the script uses: choice labels, Yes/No prompts ("...?"), client
   hints (`Affected by "<Card>": ...`).
3. `aux.Stringid(id,n)` ↔ `str(n+1)`; maximum 16.
4. When descriptions are added to an older script, the existing strings may need to move
   (string 0 becomes string 1, ...).
5. `lint.py` reports `aux.Stringid` indices whose string is empty (W030) and database
   strings the script never uses (I031).

## 8. Client-side files for custom cards

EDOPro reads extra content from `expansions/` (`*.cdb`, `script/`, `pics/`,
`strings.conf`) or from a repository declared in `config/user_configs.json` with the layout
`script/`, `pics/`, `*.cdb`, `strings.conf`, `init.lua` (wiki page "Required programs and
environment setup").
