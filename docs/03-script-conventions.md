# 03 · Script conventions (house style)

These are the conventions of the Project Ignis CardScripts repository, measured on the
13,541 official scripts and the most recent pre-release scripts (2026), plus the rules in
`MODERNIZING.md` and `CONTRIBUTING.md`. New scripts follow the **current** style even where
older scripts differ.

---

## 1. File, folder, passcode

| Card | Folder | File name |
|---|---|---|
| Released OCG/TCG card | `official/` | `c<passcode>.lua` |
| Announced but unreleased OCG/TCG card | `pre-release/` | `c<9-digit prerelease passcode>.lua` (renamed to the official passcode on release) |
| Pre-errata version | `pre-errata/` | |
| Anime / manga / video-game card | `unofficial/` | `c511xxxxxx.lua` etc. |
| Rush Duel / Speed Duel skill / GOAT format | `rush/`, `skill/`, `goat/` | |
| Custom card (Zedja) | `ZedjaCustomCards/` | `c<27xxxxxxx>.lua`, passcode from `cdb.py nextid <archetype>` (06 §5) |

* The script name must match the database passcode exactly (`c270000000.lua` for
  `270000000`). The CI checker skips passcodes with 3 digits or fewer.
* Alternate artworks have no script of their own (the database `alias` points to the
  original).
* UTF-8, LF line endings, **tabs** for indentation, no trailing whitespace
  (`.editorconfig`). Most existing files have no final newline; either is accepted.
* Keep every folder one level deep. The CI ScriptChecker scans subfolders and, depending on
  directory order, fails to load the root `proc_*.lua` libraries when a non-hidden folder
  nested two levels deep contains files (reproduced locally on 2026-09-26). New folders
  (such as `ZedjaCustomCards/`) must not have subfolders; `loadcheck.py run` warns about them.

## 2. Header

```lua
--灰流うらら                 <- line 1: official Japanese name (Japanese characters)
--Ash Blossom & Joyous Spring <- line 2: English name, identical to the database name
--scripted by Zedja           <- credit line (project decision for every new script)
local s,id=GetID()
function s.initial_effect(c)
```

* Line 1 when the Japanese name is not known yet: `--JP name` (the placeholder used by the
  current pre-release scripts). `MODERNIZING.md` allows an empty `--` as well.
* Line 2 must equal the database `name` (the linter checks it).
* Credit line: every script written for this project uses `--scripted by Zedja`
  (upstream scripts use `--scripted by X` or `--Scripted by X`). The linter checks it for
  `ZedjaCustomCards/` (S072).

## 3. Structure of `initial_effect`

Order of registration:

1. Card-level settings: `c:EnableReviveLimit()`, `c:EnableUnsummonable()`,
   `c:EnableCounterPermit(...)`, `c:SetUniqueOnField(...)`, `c:SetSPSummonOnce(id)`.
2. Summon procedure: `Fusion.AddProcMix(...)`, `Synchro.AddProcedure(...)`,
   `Xyz.AddProcedure(...)`, `Link.AddProcedure(...)`, `Pendulum.AddProcedure(c)`,
   `aux.AddEquipProcedure(c,...)` – with a comment stating the materials.
3. Card activation for Continuous/Field Spells and Continuous Traps (`e0`, no description).
4. One block per effect **in card-text order**, each preceded by a comment containing the
   effect text verbatim without the final period (the same text as the database string).
5. Global registrations at the end (`Duel.AddCustomActivityCounter`, `aux.GlobalCheck`).

After `initial_effect`: metadata, then the helper functions in the order they are used.

```lua
local s,id=GetID()
function s.initial_effect(c)
	--If this card is Normal or Special Summoned: You can add 1 "X" monster from your Deck to your hand
	local e1a=Effect.CreateEffect(c)
	e1a:SetDescription(aux.Stringid(id,0))
	e1a:SetCategory(CATEGORY_TOHAND+CATEGORY_SEARCH)
	e1a:SetType(EFFECT_TYPE_SINGLE+EFFECT_TYPE_TRIGGER_O)
	e1a:SetProperty(EFFECT_FLAG_DELAY)
	e1a:SetCode(EVENT_SUMMON_SUCCESS)
	e1a:SetCountLimit(1,{id,0})
	e1a:SetTarget(s.thtg)
	e1a:SetOperation(s.thop)
	c:RegisterEffect(e1a)
	local e1b=e1a:Clone()
	e1b:SetCode(EVENT_SPSUMMON_SUCCESS)
	c:RegisterEffect(e1b)
end
s.listed_series={SET_X}
```

Setter order used by current scripts: `SetDescription`, `SetCategory`, `SetType`,
`SetProperty`, `SetCode`, `SetRange`, `SetTargetRange`, `SetCountLimit`,
`SetCondition`, `SetCost`, `SetTarget`, `SetValue`, `SetOperation`, `SetReset`, then
`RegisterEffect`. `SetHintTiming` is placed either after `SetCountLimit` or just before
`RegisterEffect`; both occur.

## 4. Naming

* Effects: `e1`, `e2`, ... in text order; variants of one effect `e1a`, `e1b` (clones for
  "Normal or Special Summoned", ATK and DEF pairs); `e0` for the bare card activation.
* Functions: `s.<action><role>` – the corpus top names are `sptg/spop/spcon/spcost/
  spfilter` (Special Summon), `thtg/thop/thfilter` (to hand), `destg/desop/descon`,
  `tgtg/tgop/tgfilter` (to GY), `rmtg/rmop` (banish), `tdtg/tdop` (to Deck), `drtg/drop`,
  `damtg/damop`, `atktg/atkop/atkval`, `negtg/negop/negcon`, `distg/disop`, `eqtg/eqop`,
  `settg/setop`, `postg/posop`, `efftg/effop` (choose-an-effect), `cfilter`/`costfilter`
  (cost filters), `matfilter`, `splimit` (summon restrictions), `efilter` (immunity).
  Card activations of Spells/Traps traditionally use `s.target` / `s.activate`.
* Local variables: `c` = this card, `tc` = target card, `g`/`sg` = groups, `ct` = count,
  `ft` = free zones, `rc` = reason card (`re:GetHandler()`), `ec` = equipped card, `bc` =
  battle target, `p,d` = chain target player/param.
* Short 1–3 line conditions/values may be inline anonymous functions
  (`e1:SetCondition(function(e,tp,eg,ep,ev,re,r,rp) return ... end)`), which is common in
  2025–2026 scripts.

## 5. Constants and operators

* Never hardcode archetypes, card names or counters when a constant exists: `SET_*`
  (`archetype_setcode_constants.lua`), `CARD_*` and `COUNTER_*`
  (`card_counter_constants.lua`). If a card-specific value has no constant, declare a
  file-local one at the top (`local CARD_SUMMER=97254001`, `local COUNTER_SEASON=0x214`).
* Combine bit flags:
  * `+` for `EFFECT_TYPE_*`, `CATEGORY_*` and `EFFECT_FLAG_*` (house style: 7,643 / 4,760 /
    4,192 scripts use `+`, fewer than 30 use `|`);
  * `|` for `LOCATION_*`, `RESET_*`/`PHASE_*`, `REASON_*`, `RACE_*`, `ATTRIBUTE_*`,
    `TYPE_*`, `TIMING_*`, `POS_*` (MODERNIZING.md; nearly all scripts);
  * `&~` to remove bits (`RESETS_STANDARD&~RESET_TOFIELD`), `1<<n` rather than `2^n`.
* `#g` instead of `g:GetCount()`; `for tc in g:Iter() do` to iterate.

## 6. Metadata tables

| Field | When | Example |
|---|---|---|
| `s.listed_names` | The text quotes card names; include `id` when the text says `except "<own name>"` (80% of 1,130 such cards) but not when its name only appears in the once-per-turn sentence | `s.listed_names={CARD_DARK_MAGICIAN,id}` |
| `s.listed_series` | The text names archetypes | `s.listed_series={SET_RAISE_MOON}` |
| `s.listed_card_types` | The text names card types used for support ("Normal Monster", ...) | `s.listed_card_types={TYPE_NORMAL}` |
| `s.material_setcode` | Fusion/Synchro/... materials include an archetype | `s.material_setcode={SET_SYNCHRON}` |
| `s.counter_place_list` / `s.counter_list` | The card places counters / refers to counters | `s.counter_place_list={COUNTER_SPELL}` |
| `s.toss_coin` / `s.roll_dice` | Coin/dice effects | `s.toss_coin=true` |
| `s.xyz_number` | "Number N:" Xyz Monsters | `s.xyz_number=39` |

Typos in these names are silent (the linter warns on names close to a known one; upstream
has `s.listes_names`, `s.listed_seris`, ...).

## 7. Descriptions, hints and strings

* Every activated effect gets `SetDescription(aux.Stringid(id,n))`, including effects that
  are the card's only one (MODERNIZING.md). Exceptions: the bare `EFFECT_TYPE_ACTIVATE` of
  Continuous/Field/Equip/Pendulum Spells and Continuous Traps.
* `aux.Stringid(id,n)` reads database column `str(n+1)`; up to 16 strings (n = 0..15).
* String order: effect descriptions in text order first (n = 0, 1, ...), then extra
  strings (choices, Yes/No prompts, client hints) in the order the script uses them.
* String wording, as in the database:
  * effect description = the effect text without the final period (current style keeps the
    full text; older cards use short labels);
  * choice labels = the bullet text ("Special Summon 1 monster from your GY");
  * Yes/No prompts end with "?" ("Special Summon 1 Level 1 Dragon monster from your Deck?");
  * client hints for lingering restrictions: `Affected by "<Card>": <restriction>`, or a
    short "Cannot ..." label.
* Before every player selection: `Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_...)` with the
  message that matches the action (`HINTMSG_ATOHAND` search, `HINTMSG_RTOHAND` return,
  `HINTMSG_SPSUMMON`, `HINTMSG_DESTROY`, `HINTMSG_REMOVE`, `HINTMSG_TOGRAVE`,
  `HINTMSG_TODECK`, `HINTMSG_FACEUP`, `HINTMSG_TARGET`, `HINTMSG_EQUIP`, `HINTMSG_SET`,
  `HINTMSG_XMATERIAL`, `HINTMSG_NEGATE`, `HINTMSG_CONFIRM`, `HINTMSG_DISCARD`).
* Cards selected without targeting that the opponent should see: `Duel.HintSelection(g)`;
  cards added from the Deck to the hand: `Duel.ConfirmCards(1-tp,g)`.
* Quick Effects get `SetHintTiming` so the client prompts at the right moments. Common
  values: `SetHintTiming(0,TIMING_STANDBY_PHASE|TIMING_MAIN_END|TIMINGS_CHECK_MONSTER_E)`,
  `SetHintTiming(0,TIMINGS_CHECK_MONSTER_E)`, `SetHintTiming(0,TIMING_END_PHASE)`,
  `SetHintTiming(TIMING_DAMAGE_STEP)` (stat changes), `SetHintTiming(0,TIMING_MAIN_END)`
  (Main Phase only).

## 8. Modern idioms (MODERNIZING.md, condensed)

1. UTF-8, LF, Japanese + English name header.
2. Description on (almost) every activated effect; update database strings accordingly.
3. Descriptive one-line effect comments, capitalized game terms.
4. `SET_` constants instead of hex setcodes (create the constant if missing).
5. Hint timings on Quick Effects.
6. No `EFFECT_FLAG_DAMAGE_STEP` on SINGLE triggers unless a ruling requires it.
7. No `if tc and` around targets except in mandatory effects.
8. `Duel.SetPossibleOperationInfo` for optional/uncertain parts.
9. `Duel.GetMZoneCount(tp,<leaving cards>)` when the cost/effect frees a zone.
10. `Duel.SelectEffect` for "choose 1" effects.
11. `Cost.*` helpers for standard costs.
12. `Card.IsCanBeXyzMaterial` before attaching.
13. `aux.SelectUnselectGroup` for selections with combined conditions.
14. Constants instead of magic effect codes (`EFFECT_SYNSUB_NORDIC`, ...).
15. Bitwise operators for bitsets (see §5 for the house exception).
16. No handler `IsRelateToEffect` check just to model "must remain face-up" on continuous
    Spells/Traps.

## 9. Things that are never done

* Using `io`, `os`, `require`, `dofile`, `loadfile` (not available in the client).
* Defining new global functions or tables from a card script (use `s.` or `local`).
* Hardcoding another card's effect code as a number when a constant exists.
* Writing to `Card`, `Duel`, `aux` from a card script (upstream has one such case,
  `Cost.SelfTribute2`; do not copy it).
