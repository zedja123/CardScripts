# ZedjaCustomCards

Custom cards by Zedja: scripts (`c<passcode>.lua`) and their database
(`ZedjaCustomCards.cdb`) live together in this folder.

| Rule | Value |
|---|---|
| Credit line (line 3 of every script) | `--scripted by Zedja` |
| Database | `ZedjaCustomCards.cdb` (scope/`ot` = Custom, 0x20) |
| Passcodes | `270000000 + 100 × (archetype − 1) + n`: archetype 1 = `270000000`–`270000099`, archetype 2 = `270000100`–`270000199`, ... |
| Tokens | Taken from the end of the archetype's block (`...99`, `...98`, ...) |
| Archetype setcodes (default, not yet confirmed) | `0xE00 + archetype number` (archetype 1 = `0xe01`), declared as a file-local `SET_` constant in each script |
| Pull requests | One per batch; if a card needs code review, one per card afterwards |

Keep this folder flat (no subfolders): the CI script checker can fail when a folder nested
two levels deep contains files.

Tools (from the repository root):

```bash
T=.claude/skills/edopro-card-scripting/tools
python3 $T/cdb.py nextid 1                 # next free passcode for custom archetype 1
python3 $T/cdb.py new card.json --write    # adds the row to ZedjaCustomCards.cdb
python3 $T/lint.py ZedjaCustomCards/       # also checks the rules above
python3 $T/loadcheck.py run ZedjaCustomCards/c270000000.lua
```

To use the cards in EDOPro, copy `ZedjaCustomCards.cdb` to `expansions/` and the scripts to
`expansions/script/` (or point a repository entry in `config/user_configs.json` at a
repository with `script/` and the database at its root).
