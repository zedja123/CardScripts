# CardScripts (EDOPro card scripts, Lua 5.4)

When asked to script, fix or review a card, follow the skill
`.claude/skills/edopro-card-scripting/SKILL.md`. Human-readable reference:
`docs/`.

Quick commands (from this folder):

```bash
T=.claude/skills/edopro-card-scripting/tools
python3 $T/cdb.py show <passcode|name>      # card data, strings, script path
python3 $T/cdb.py analogs <passcode>        # scripted cards with similar wording
python3 $T/lint.py <script>                 # static checks
python3 $T/loadcheck.py run <script>        # load test in the real core (run `setup` once)
```

Repository rules: tabs, LF, UTF-8; one script per card named `c<passcode>.lua`; see
`MODERNIZING.md` and `CONTRIBUTING.md`.

Project decisions: credit `--scripted by Zedja`; custom cards in `ZedjaCustomCards/` with
`ZedjaCustomCards/ZedjaCustomCards.cdb`; passcodes `270000000 + 100*(archetype-1) + n`
(`cdb.py nextid`); one pull request per batch. Keep every folder one level deep (CI checker).
