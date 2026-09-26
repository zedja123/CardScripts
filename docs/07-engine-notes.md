# 07 · How ygopro-core runs a card script

Notes taken from the ygopro-core sources (`interpreter.cpp`, `effect.cpp`, `libeffect.cpp`,
`processor.cpp`, `operations.cpp`) and the Lua libraries in CardScripts. They explain *why*
the conventions exist, which is what makes unusual cards scriptable.

---

## 1. Loading

* A duel creates one Lua 5.4 state. `constant.lua` and `utility.lua` are loaded first;
  `utility.lua` then loads `chain.lua`, `cards_specific_functions.lua`, every `proc_*.lua`
  and `deprecated_functions.lua` (and `proc_unofficial.lua` from the unofficial folder).
* Safe environment: `io`, `os`, `debug`, `require`, `dofile`, `loadfile` and
  `collectgarbage` are unavailable in the client. Never use them; `print` output is not
  shown either (use `Debug.Message`).
* When a card is created the core loads `c<passcode>.lua` once per passcode into a table
  `c<passcode>`, whose metatable is `Card`. `GetID()` returns that table and the passcode
  (`self_table`, `self_code`), which is why every script starts with
  `local s,id=GetID()`.
* Alternate artworks: if the database `alias` is within 10 of the passcode, the alias's
  script is loaded instead (`register_card`).
* `s.initial_effect(c)` is then called for every card instance. It is **optional only for
  non-Pendulum Normal Monsters**; for any other card a missing `initial_effect` is an
  error.
* Script-level data (`s.listed_names`, `s.material_setcode`, ...) is shared by all copies of
  the card because it lives in the per-passcode table.

## 2. Objects

| Object | Created by | Lives |
|---|---|---|
| `Card` | the core | whole duel; a card that changes location becomes "a new card" for relations and resets |
| `Effect` | `Effect.CreateEffect(owner)`, `Effect.GlobalEffect()`, `e:Clone()` | until reset or the owner is removed |
| `Group` | `Duel.Get*Group`, `Group.CreateGroup()`, selections | garbage-collected unless `g:KeepAlive()` (then call `g:DeleteGroup()` when done) |

Effect terminology: the **owner** is the card that created it, the **handler** is the card
it is registered to (`c:RegisterEffect(e)`), or no card when registered to a player
(`Duel.RegisterEffect(e,player)`). `e:GetHandler()`, `e:GetOwner()`,
`e:GetHandlerPlayer()` / `e:GetOwnerPlayer()` read them.

## 3. From activation to resolution

For an activated effect (`EFFECT_TYPE_ACTIONS`: ignition, trigger, quick, flip,
activate):

1. **Legality** (`effect::is_activateable`): count limit available; location and
   face-up requirements; Damage Step rules (§6); `EFFECT_CANNOT_ACTIVATE` and
   `EFFECT_ACTIVATE_COST` from other cards; then `condition(e,tp,eg,ep,ev,re,r,rp)`,
   `cost(...,chk=0)`, `target(...,chk=0)`. All three must return true.
2. **Activation**: the count limit is consumed (`dec_count`); a Spell/Trap is flipped
   face-up/placed; `cost(...,chk=1)` pays the cost; `target(...,chk=1)` selects targets and
   records operation info; `EVENT_BECOME_TARGET` is raised for targeted cards;
   `EVENT_CHAINING` is raised (other cards may respond).
3. **Resolution**: when the Chain resolves, `operation(e,tp,eg,ep,ev,re,r,rp)` runs. If the
   activation was negated, the operation does not run; with `EFFECT_COUNT_CODE_OATH` the
   count is given back, and `EFFECT_FLAG_OATH` lingering effects created during
   activation are removed.

Consequences:

* `chk==0` must be **side-effect free** and must mirror what the resolution needs. Anything
  done after `if chk==0 then return ... end` happens on activation only.
* Whatever is decided on activation (choices, costs paid, values) must be passed to the
  resolution explicitly: targets via `Duel.SetTargetCard`/`SelectTarget`, numbers via
  `Duel.SetTargetParam`, choices via `e:SetLabel` or, better, `e:GetChainData()` (a table
  unique to the chain link, cleared at the end of the Chain; see `chain.lua`).
* `chkc` exists for target redirection (e.g. *Cairngorgon, Antiluminescent Knight*): the
  core calls `target(...,chk=0,chkc=card)` asking "would `card` be a legal target?". Every
  targeting effect returns that check first: `if chkc then return <same filter as the
  selection> end`.
* The Chain is processed on the core side; the functions are Lua coroutines, so selections
  and prompts inside them are fine.

## 4. Function parameters

`condition(e,tp,eg,ep,ev,re,r,rp)`, `cost(e,tp,eg,ep,ev,re,r,rp,chk)`,
`target(e,tp,eg,ep,ev,re,r,rp,chk,chkc)`, `operation(e,tp,eg,ep,ev,re,r,rp)`.

* `e` the effect, `tp` the player activating it.
* For triggers/chain responses the rest describe the **event** (`raise_event(eg, code, re,
  r, rp, ep, ev)` in the core):

| Event | `eg` | `ep` | `ev` | `re` / `r` / `rp` |
|---|---|---|---|---|
| `EVENT_CHAINING` | handler of the activated effect | activating player | chain link number | `re` = activated effect, `rp` = activating player |
| `EVENT_SUMMON_SUCCESS`, `EVENT_SPSUMMON_SUCCESS` | summoned card(s) | summoning player (may be `PLAYER_NONE` for effect summons) | 0 | summon procedure or effect |
| `EVENT_TO_GRAVE`, `EVENT_REMOVE`, `EVENT_TO_HAND`, `EVENT_TO_DECK`, `EVENT_DESTROYED`, `EVENT_LEAVE_FIELD` | moved card(s) | – | – | reason effect / reason bits / reason player |
| `EVENT_BE_MATERIAL` | the materials | summoning player | – | `r` = `REASON_SYNCHRO`, `REASON_XYZ`, ... ; `c:GetReasonCard()` = the summoned monster |
| `EVENT_ATTACK_ANNOUNCE` | attacker | turn player | – | – |
| `EVENT_BATTLE_DESTROYING` / `EVENT_BATTLE_DESTROYED` | destroying / destroyed monsters | – | – | – |
| `EVENT_DAMAGE` | reason card | damaged player | amount | reason effect/bits/player |

For SINGLE effects the handler itself is the subject; read its history with
`c:IsPreviousLocation`, `c:IsPreviousControler`, `c:IsPreviousPosition`, `c:IsReason`,
`c:GetReasonPlayer`, `c:IsSummonLocation`, `c:IsSummonType`/`IsXSummoned()`.

## 5. Relations: `IsRelateToEffect`

A card is "related" to a chain link if it is the handler of an activated effect or one of
its targets, and it has not left the zone since. In the resolution:

* Operations on **this card** check `c:IsRelateToEffect(e)` (and `c:IsFaceup()` where
  relevant).
* Operations on **targets** check `tc:IsRelateToEffect(e)` (use `Duel.GetTargetCards(e)`
  for several targets).
* Do **not** write `if tc and ...` except for mandatory effects, where a target may not
  exist (MODERNIZING.md).
* Continuous/Field/Equip Spells and Continuous Traps that must stay face-up to resolve are
  handled by the core (`CHAIN_CONTINUOUS_CARD`); do not add a handler relation check for
  that purpose.
* `proc_workaround.lua` redefines `Card.IsRelateToEffect` to use `IsRelateToChain` while a
  chain resolves, fixing multi-activation cases. Keep calling `IsRelateToEffect`.

## 6. Damage Step legality

`effect::is_activateable` refuses activation in `PHASE_DAMAGE` / `PHASE_DAMAGE_CAL` unless
the effect has `EFFECT_FLAG_DAMAGE_STEP` / `EFFECT_FLAG_DAMAGE_CAL`, with two exceptions:

* battle events `EVENT_BATTLE_START` (1132) to `EVENT_BATTLE_DAMAGE` (1143);
* SINGLE optional triggers, mandatory triggers and flip effects.

So: add the flag to Quick Effects and FIELD triggers that the text allows in the Damage
Step; add `not Duel.IsDamageStep()` to SINGLE optional triggers whose text says "(except
during the Damage Step)"; never add the flag to SINGLE triggers without a ruling.

## 7. Count limits

`Effect.SetCountLimit(count[, code | {code,index}[, flags]])` (`libeffect.cpp`):

* no code: soft limit stored on the effect;
* code: hard limit stored in the field per `(code, index, player)`; `id` and `{id,0}` are the
  same key;
* `EFFECT_COUNT_CODE_OATH` (0x1): given back if the activation is negated;
* `EFFECT_COUNT_CODE_DUEL` (0x2): never resets; requires a code;
* `EFFECT_COUNT_CODE_SINGLE` (0x4): counted per card instance (field id);
* `EFFECT_COUNT_CODE_CHAIN` (0x8): resets at the end of the Chain; with code 0 it becomes
  per card instance.

## 8. Setters that accept `nil` silently

`Effect.SetCondition`, `SetCost` and `SetTarget` raise an error for `nil`, which the CI
checker catches in `initial_effect`. **`SetOperation(nil)` and `SetValue(nil)` are
accepted silently** (`libeffect.cpp`): a misspelled `s.operatoin` creates an effect that
does nothing. The linter's E012 rule ("s.x used but never defined") exists for this.

## 9. Resets

| Want | `SetReset` |
|---|---|
| Until the card leaves the field / is flipped / etc. | `RESET_EVENT\|RESETS_STANDARD` |
| "until the end of this turn" on a card | `RESETS_STANDARD_PHASE_END` (= `RESET_EVENT\|RESETS_STANDARD\|RESET_PHASE\|PHASE_END`) |
| Same, but also lost if the card's effects are negated | `RESETS_STANDARD_DISABLE_PHASE_END` |
| Player effect "for the rest of this turn" | `RESET_PHASE\|PHASE_END` (registered with `Duel.RegisterEffect(e,tp)`) |
| "until the end of your opponent's turn" | `RESET_PHASE\|PHASE_END\|RESET_OPPO_TURN` (or with a count, see corpus) |
| "... next turn" | `RESET_PHASE\|PHASE_END,2` |
| Only during this Chain | `RESET_CHAIN` |
| `EFFECT_LEAVE_FIELD_REDIRECT` ("banish it when it leaves the field") | `RESET_EVENT\|RESETS_REDIRECT` |

`RESETS_STANDARD` covers leaving the field, going to hand/deck/GY/banishment, temporary
banishment and being turned face-down. Remove bits with `&~` (e.g.
`RESETS_STANDARD&~RESET_TOFIELD`).

## 10. Operation info and categories

* `SetCategory` declares what the effect **can** do; other cards read it (e.g. *Ash
  Blossom* checks `CATEGORY_SEARCH`, `CATEGORY_SPECIAL_SUMMON`, `CATEGORY_DECKDES`).
* `Duel.SetOperationInfo(0,category,targets,count,player,param)` states what this
  activation **will** do: for known cards pass the group; for cards not yet chosen pass
  `nil` with the player and location in `param` (e.g. `nil,1,tp,LOCATION_DECK`).
* `Duel.SetPossibleOperationInfo` for optional or uncertain parts ("you can", coin
  results).
* When the category depends on a choice made on activation, call `e:SetCategory(...)` in
  the target function after the choice.

## 11. Lingering, global and flag effects

* Lingering effects created on resolution (`Duel.RegisterEffect(e1,tp)`) are how "for the
  rest of this turn" restrictions work. Give them `EFFECT_FLAG_CLIENT_HINT` and a
  description, or use `aux.RegisterClientHint(c,nil,tp,1,0,aux.Stringid(id,n))`, so the
  player sees the restriction.
* Global trackers (e.g. "if a monster was Special Summoned this turn") are registered once
  per duel with `aux.GlobalCheck(s,function() ... end)` using `Effect.GlobalEffect()`.
* `c:RegisterFlagEffect(id,reset,property,count)` / `Duel.RegisterFlagEffect` store
  markers; test with `c:HasFlagEffect(id)` / `Duel.HasFlagEffect(tp,id)`.
* Activity counters (`Duel.AddCustomActivityCounter`, `Duel.GetCustomActivityCount`) track
  summons/activations earlier in the turn; used by "the turn you activate this effect"
  locks.
* Granted effects (`EFFECT_TYPE_FIELD+EFFECT_TYPE_GRANT` with the effect as label object)
  are cloned onto every affected card, and the engine sets each clone's **owner to the
  receiving card** (`field::adjust_grant_effect`). Inside a granted effect, `e:GetOwner()`
  and `e:GetHandler()` are the card that gained it, never the card that grants it. To refer
  to the granting card, find it on the field or capture it in a closure in
  `initial_effect`. ("Build Rider - Kiryu" used `e:GetOwner()` in a procedure granted to
  Extra Deck monsters, so the procedure was never available.)

## 12. Summon procedures and summon types

* Extra Deck and Ritual monsters call `c:EnableReviveLimit()` and register their procedure
  (`Fusion.AddProcMix`, `Synchro.AddProcedure`, `Xyz.AddProcedure`, `Link.AddProcedure`),
  which defines `SUMMON_TYPE_*`.
* Check how a monster was summoned with `c:IsFusionSummoned()`, `IsSynchroSummoned()`,
  `IsXyzSummoned()`, `IsLinkSummoned()`, `IsRitualSummoned()`, `IsPendulumSummoned()`,
  `IsNormalSummoned()`, `IsSpecialSummoned()`; the location with `c:IsSummonLocation(...)`.
* Inherent summons (`EFFECT_SPSUMMON_PROC`) do not use the Chain: their
  `condition(e,c)` / `target(e,tp,eg,ep,ev,re,r,rp,chk,c)` / `operation(...,c)` signatures
  differ (the card being summoned is the last parameter; `c==nil` in the condition means
  "is the procedure available at all").

## 13. Recent core behaviour worth knowing (2026)

* `Duel.IsPlayerCanSpecialSummonMonster` now needs only 2 parameters (commit `e25f3f5`,
  2026-05-03).
* `Duel.ConfirmDecktop` / `Duel.ConfirmExtratop` return the confirmed group (2026-06).
* `CHAININFO_TRIGGERING_LINK`, `CHAININFO_TRIGGERING_LSCALE`/`RSCALE` exist (2026-06).
* `PLAYER_EITHER` (4) is a Lua-only helper constant.
* `EFFECT_OPPO_CHOOSES_SPSUMMON_ZONE` constants were added (2026-09).

When in doubt about any behaviour, read the corresponding `LUA_FUNCTION(...)` in
`lib*.cpp`, or the Lua definition in the CardScripts root files; they are the authority.
