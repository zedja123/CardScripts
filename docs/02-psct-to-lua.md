# 02 · Reading card text (PSCT) and mapping it to Lua

Problem-Solving Card Text (PSCT) is Konami's standardized card-text grammar. Every
punctuation mark and connective has a defined rules meaning, and EDOPro scripts encode
those meanings directly. Reading the text precisely is therefore the first half of
scripting a card.

> **Source note.** The official PSCT pages on yugioh-card.com could not be fetched from
> this environment (the host is blocked by the network policy). This chapter is built from
> established PSCT knowledge and, above all, from the card corpus itself: every mapping
> below was checked against the official scripts that implement the same wording (the
> percentages are "scripts that use the construct / scripts whose text has the wording").
> Rows marked *verify* should be confirmed against the official PSCT page or a ruling.

---

## 1. Split the text into effects

1. Material lines and summon conditions come first (Fusion/Synchro/Xyz/Link materials,
   "Cannot be Normal Summoned/Set", "Must be Special Summoned by ...").
2. Every sentence (or group of sentences sharing one activation) that contains a **colon
   `:`** or a **semicolon `;`** is an **activated effect**: it starts a Chain.
   `FLIP:` effects are activated effects as well.
3. Sentences with neither are **continuous effects**, **summoning procedures**, or
   **restrictions**, and never start a Chain, with one exception: on a Normal or Quick-Play
   Spell, Ritual Spell, or Normal/Counter Trap, the text is the effect of **activating the
   card itself** ("Draw 2 cards." is scripted as an `EFFECT_TYPE_ACTIVATE` effect even
   without a colon or semicolon).
4. Pendulum Monsters have two blocks: `[ Pendulum Effect ]` (works in the Pendulum Zone,
   `SetRange(LOCATION_PZONE)`) and `[ Monster Effect ]`.
5. The "once per turn" sentence at the end applies to the effects it names (see §5).

Record the result as an **effect table** before writing code (the workflow requires it):

| # | Text (verbatim, without the final period) | Kind | Range | Trigger/event | OPT | Cost | Target | Resolution |
|---|---|---|---|---|---|---|---|---|

---

## 2. Anatomy of an activated effect

```
[activation condition / timing] : [cost and/or targeting] ; [resolution]
```

| Text part | Where it goes in the script | Notes |
|---|---|---|
| Before the colon: "If ...", "When ...", "During ...", "(Quick Effect)" | `SetType`, `SetCode` (event), `SetCondition` | Also the range: where the card must be (`SetRange`) |
| Between colon and semicolon: "You can pay 1000 LP;", "discard 1 card;", "Tribute this card;" | `SetCost` | Paid on activation; cannot be responded to |
| "target ..." (always before the semicolon) | `SetProperty(EFFECT_FLAG_CARD_TARGET)` + selection in `SetTarget` (`Duel.SelectTarget`) + `chkc` branch | Targets are chosen on activation |
| After the semicolon | `SetOperation` | Everything that happens on resolution |
| No semicolon | No cost, no targets | The whole text after the colon is the resolution |
| "You can" | Optional (`_O` types, or `SelectYesNo` inside a resolution) | Absence of "You can" in a trigger means mandatory (`_F`) |

The `SetTarget` function also carries the **activation legality check** (`chk==0`): the
effect may only be activated if it could do what it says (e.g. a card to search exists).

---

## 3. Effect kinds and their `SetType`

| Text pattern | Kind | `SetType` | Typical `SetCode` / range |
|---|---|---|---|
| "You can ...;" with no condition, monster/Spell/Trap on the field or in hand/GY | Ignition (Spell Speed 1) | `EFFECT_TYPE_IGNITION` | `SetRange(LOCATION_MZONE / HAND / GRAVE / SZONE / FZONE / PZONE)` |
| "(Quick Effect): You can ..." | Quick Effect (Spell Speed 2) | `EFFECT_TYPE_QUICK_O` (98% of 1,196 cards) | `EVENT_FREE_CHAIN`, or `EVENT_CHAINING` for "When ... is activated" |
| "If/When <event>: You can ..." about **this card** | Optional trigger | `EFFECT_TYPE_SINGLE+EFFECT_TYPE_TRIGGER_O` | Event such as `EVENT_SUMMON_SUCCESS`, `EVENT_TO_GRAVE` |
| "If/When <event>: ..." about **other cards / the game** | Optional trigger | `EFFECT_TYPE_FIELD+EFFECT_TYPE_TRIGGER_O` | Event + `SetRange` where this card must be |
| Same without "You can" | Mandatory trigger | `..._TRIGGER_F` | Never needs `EFFECT_FLAG_DELAY` |
| "FLIP: ..." | Flip effect | `EFFECT_TYPE_SINGLE+EFFECT_TYPE_FLIP` | No code needed |
| Normal/Quick-Play Spell, Normal/Counter Trap card activation | Card activation | `EFFECT_TYPE_ACTIVATE` | `EVENT_FREE_CHAIN` or an event |
| Continuous/Field/Equip Spell, Continuous Trap | Activation + separate effects | `e0: EFFECT_TYPE_ACTIVATE, EVENT_FREE_CHAIN` then other effects with `SetRange(LOCATION_SZONE/FZONE)` | The bare activation has no description |
| "Monsters you control gain ...", "Your opponent cannot ..." | Continuous (field) | `EFFECT_TYPE_FIELD` | `SetCode(EFFECT_...)`, `SetRange`, `SetTargetRange` |
| "This card gains ...", "Cannot be destroyed by ..." | Continuous (self) | `EFFECT_TYPE_SINGLE` + `EFFECT_FLAG_SINGLE_RANGE` | `SetRange(LOCATION_MZONE)` |
| "The equipped monster gains ..." | Continuous (equip) | `EFFECT_TYPE_EQUIP` | Registered on the Equip Card |
| "An Xyz Monster that has this card as material gains ..." | Granted to the Xyz Monster | `EFFECT_TYPE_XMATERIAL` (+ `IGNITION`/`TRIGGER_O`/... for activated ones) | |
| "You can Special Summon this card (from your hand) by ..." / "If ..., you can Special Summon this card (from your hand)" | Inherent summon procedure (no Chain) | `EFFECT_TYPE_FIELD` + `SetCode(EFFECT_SPSUMMON_PROC)` + `EFFECT_FLAG_UNCOPYABLE` | `SetRange(LOCATION_HAND)` |

---

## 4. "If" vs "When", timing words and the Damage Step

| Wording | Meaning | Script |
|---|---|---|
| "**If** X: You can ..." | Optional trigger that **cannot miss the timing** | `EFFECT_FLAG_DELAY` (640 of 641 "If this card is ... Special Summoned: You can") |
| "**When** X: You can ..." | Optional trigger that **can miss the timing** (X must be the last thing that happened) | **No** `EFFECT_FLAG_DELAY` (only 10 of 106 "When this card is ... Special Summoned: You can" have it, mostly errata/legacy) |
| Mandatory trigger (no "You can") | Never misses timing | No `EFFECT_FLAG_DELAY` (1,833 of 1,866 mandatory triggers) |
| "When your opponent activates ..." / "When a card or effect is activated ..." | Chain response | `EVENT_CHAINING` + `SetCondition(... rp==1-tp ...)` |
| "During the Main Phase (Quick Effect)" | Condition | `SetCondition(function() return Duel.IsMainPhase() end)` + `SetHintTiming(0,TIMING_MAIN_END\|...)` |
| "During your opponent's turn" | Condition | `Duel.IsTurnPlayer(1-tp)` |
| "During the End Phase:" / "At the start of the Battle Phase:" | Phase trigger | `SetCode(EVENT_PHASE+PHASE_END)` / `EVENT_PHASE+PHASE_BATTLE_START`, `EFFECT_TYPE_FIELD+TRIGGER_O/F`, `SetRange` |
| "(except during the Damage Step)" on a **SINGLE** optional trigger | SINGLE+TRIGGER_O effects are allowed in the Damage Step by the core, so exclude it | `SetCondition(... not Duel.IsDamageStep())` |
| "(except during the Damage Step)" on a **FIELD** trigger or Quick Effect | Already the default: the core refuses these in the Damage Step unless `EFFECT_FLAG_DAMAGE_STEP` is set | Nothing to add |
| Stat-changing Quick Effect usable in the Damage Step | Needs the flag and the "before damage calculation" check | `SetProperty(EFFECT_FLAG_DAMAGE_STEP)` + `SetCondition(aux.StatChangeDamageStepCondition)` + `SetHintTiming(TIMING_DAMAGE_STEP)` |
| Chain responses that negate ("negate the activation") | Usually allowed in the Damage Step | `EFFECT_FLAG_DAMAGE_STEP+EFFECT_FLAG_DAMAGE_CAL` (222 of 243 such Quick Effects) |

Core detail (ygopro-core `effect.cpp`, `is_activateable`): outside battle events
(`EVENT_BATTLE_START`..`EVENT_BATTLE_DAMAGE`, codes 1132–1143), an effect can only be
activated in the Damage Step if it has `EFFECT_FLAG_DAMAGE_STEP`, **except** SINGLE
optional triggers, mandatory triggers and flip effects. That is why the MODERNIZING guide
says not to add the flag to SINGLE triggers.

---

## 5. Usage limits ("once per turn" family)

| Text | Script | Corpus check |
|---|---|---|
| "Once per turn: ..." (soft; per copy) | `e:SetCountLimit(1)` | 91% of 2,089 |
| "You can only use this effect of "X" once per turn." | `e:SetCountLimit(1,id)` | 91% of 1,934 (the rest use OATH for card activations) |
| "You can only use each effect of "X" once per turn." | `SetCountLimit(1,{id,0})`, `SetCountLimit(1,{id,1})`, ... one index per effect | 97% of 1,818 |
| "You can only use 1 "X" effect per turn, and only once that turn." | The **same** `SetCountLimit(1,id)` on every listed effect (shared counter) | 99% of 248 |
| "You can only activate 1 "X" per turn." | `SetCountLimit(1,id,EFFECT_COUNT_CODE_OATH)` on the card activation | 97% of 931 |
| "You can only Special Summon "X" once per turn this way." | `SetCountLimit(1,id,EFFECT_COUNT_CODE_OATH)` on the `EFFECT_SPSUMMON_PROC` | 90% (+6% with `{id,n}`) of 200 |
| "You can only Special Summon "X" once per turn." (any method) | `c:SetSPSummonOnce(id)` | 100% of 76 |
| "You can only control 1 "X"." | `c:SetUniqueOnField(1,0,id)` | 92% of 132 |
| "Once per Chain" (per copy) | `SetCountLimit(1,0,EFFECT_COUNT_CODE_CHAIN)` (most common) or `SetCost(Cost.SoftOncePerChain(id))` | |
| "You can only use this effect of "X" once per Chain" (per name) | `SetCost(Cost.HardOncePerChain(id))` | |
| "once per Duel" | `SetCountLimit(1,id,EFFECT_COUNT_CODE_DUEL)` | |
| "Once per battle" | `SetCost(Cost.SoftOncePerBattle(id))` (per copy) / `SetCost(Cost.HardOncePerBattle(id))` (per name) | |

Why these exact forms (verified in ygopro-core `libeffect.cpp` and `effect.cpp`):

* `SetCountLimit(count, code_or_{code,index}, flags)`. `SetCountLimit(1,id)` and
  `SetCountLimit(1,{id,0})` use **the same counter** (index 0), so "each effect" needs
  distinct indices.
* Hard limits (with a code) are counted per player: if the opponent takes control of the
  card, they have their own counter.
* `EFFECT_COUNT_CODE_OATH`: if the activation is negated, the count is given back
  (`processor.cpp`), which matches "you can only **activate**". Without OATH, a negated
  activation still consumes the use ("you can only **use**").
* Soft limits (no code) live on the effect object; "Once per turn" applies per copy.

---

## 6. Resolution connectives

| Connective | Meaning | Script |
|---|---|---|
| "A, **and if you do**, B" | B only if A was performed; A and B are simultaneous | `if <A succeeded> then <B> end` with **no** `Duel.BreakEffect()` (`Duel.SpecialSummon(...)>0`, `Duel.Destroy(...)>0`, `tc:IsLocation(...)` after the move) |
| "A, **then** B" | B only if A was performed; B happens **after** A (not simultaneous) | `if <A succeeded> then Duel.BreakEffect() <B> end` |
| "A, **then you can** B" | As "then", and B is optional | `if <A succeeded> and <B possible> and Duel.SelectYesNo(tp,aux.Stringid(id,n)) then Duel.BreakEffect() <B> end` |
| "A, **also** B" / "Also, B" | Independent: B applies even if A did not happen *(verify simultaneity against the official page)* | Perform B unconditionally; lingering restrictions ("also, for the rest of this turn ...") are registered regardless of A (only 14% of "also" scripts use `BreakEffect`) |
| "A **and** B" | Both done together | Perform both, no `BreakEffect` |
| "A **or** B" / "either ... or ..." | A choice (who chooses and when is stated by the text) | `Duel.SelectOption` / `Duel.SelectEffect` in the operation |
| "**Activate** 1 of these effects;" + bullets | Choice made **on activation** | `Duel.SelectEffect` in `SetTarget`; store the choice (`e:SetLabel(op)` or `e:GetChainData().choice`); set the category per choice |
| "**Apply** 1 of these effects" / "choose 1" in the resolution | Choice made **on resolution** | `Duel.SelectEffect` in `SetOperation` |
| "... **except** "X"" | Exclusion in the filter | `not c:IsCode(<X>)`; when X is this card, `not c:IsCode(id)` and add `id` to `s.listed_names` |

Corpus checks: "then" → `Duel.BreakEffect` in 50% of 2,814 scripts (many "then" clauses sit
in costs or text that does not need a break, e.g. "banish this card, then target"); "and
if you do" → 18% (the break appears only when a *later* "then" follows).

---

## 7. Costs

| Text before the semicolon | Script |
|---|---|
| "You can Tribute this card;" | `SetCost(Cost.SelfTribute)` |
| "You can banish this card from your GY;" | `SetCost(Cost.SelfBanish)` |
| "You can discard this card;" | `SetCost(Cost.SelfDiscard)` |
| "You can send this card to the GY;" | `SetCost(Cost.SelfToGrave)` |
| "You can reveal this card in your hand;" | `SetCost(Cost.SelfReveal)` |
| "You can detach 1 material from this card;" | `SetCost(Cost.DetachFromSelf(1))` (min, max, op) |
| "You can pay 1000 LP;" / "pay half your LP;" | `SetCost(Cost.PayLP(1000))` / `Cost.PayLP(1/2)` |
| "You can discard 1 card;" / "... 1 other card" | `SetCost(Cost.Discard())` / `Cost.Discard(nil,true)` / `Cost.Discard(filter)` |
| "You can reveal 1 "X" monster in your hand;" | `SetCost(Cost.Reveal(filter))` |
| "You can remove 2 X Counters from this card;" | `SetCost(Cost.RemoveCounterFromSelf(COUNTER_X,2))` |
| Two costs together | `Cost.AND(costA,costB)` |
| "Tribute 1 monster;" | `Duel.CheckReleaseGroupCost` / `Duel.SelectReleaseGroupCost` |
| Anything else | A custom `s.xxxcost(e,tp,eg,ep,ev,re,r,rp,chk)`: `if chk==0 then return <can pay> end` then pay with `REASON_COST` |

If paying the cost frees a Monster Zone that the effect then uses, check zones with
`Duel.GetMZoneCount(tp,<card(s) leaving>)` instead of `Duel.GetLocationCount`.

---

## 8. Frequent phrases

| Phrase | Script building block |
|---|---|
| "add ... from your Deck to your hand" | `CATEGORY_TOHAND+CATEGORY_SEARCH`, `Duel.SendtoHand(g,nil,REASON_EFFECT)` + `Duel.ConfirmCards(1-tp,g)`, hint `HINTMSG_ATOHAND` |
| "add ... from your GY to your hand" | `CATEGORY_TOHAND` (targeted: `SetOperationInfo(0,CATEGORY_TOHAND,g,1,tp,0)`) |
| "return ... to the hand" (from the field) | `CATEGORY_TOHAND`, hint `HINTMSG_RTOHAND` |
| "Special Summon" | `CATEGORY_SPECIAL_SUMMON`, `c:IsCanBeSpecialSummoned(e,0,tp,false,false)`, `Duel.GetLocationCount(tp,LOCATION_MZONE)>0` (Extra Deck: `Duel.GetLocationCountFromEx`) |
| "Special Summon ... in Defense Position" | `POS_FACEUP_DEFENSE` in both the check and the summon |
| "send ... to the GY" | `CATEGORY_TOGRAVE`, `Duel.SendtoGrave(g,REASON_EFFECT)`; "from the Deck" also `CATEGORY_DECKDES` only for mills of the top cards |
| "banish" | `CATEGORY_REMOVE`, `Duel.Remove(g,POS_FACEUP,REASON_EFFECT)` |
| "banish ... until the End Phase" | `aux.RemoveUntil(g,nil,REASON_EFFECT,PHASE_END,id,e,tp,aux.DefaultFieldReturnOp)` |
| "destroy" | `CATEGORY_DESTROY`, `Duel.Destroy(g,REASON_EFFECT)` |
| "shuffle into the Deck" | `CATEGORY_TODECK`, `Duel.SendtoDeck(g,nil,SEQ_DECKSHUFFLE,REASON_EFFECT)` |
| "place on the bottom of the Deck" | `Duel.SendtoDeck(g,nil,SEQ_DECKBOTTOM,REASON_EFFECT)` |
| "draw" | `CATEGORY_DRAW`, `Duel.SetTargetPlayer` / `SetTargetParam` + `Duel.Draw(p,d,REASON_EFFECT)` |
| "inflict X damage" | `CATEGORY_DAMAGE`, `Duel.Damage(1-tp,X,REASON_EFFECT)` |
| "gain X LP" | `CATEGORY_RECOVER`, `Duel.Recover(tp,X,REASON_EFFECT)` |
| "negate the activation" | `CATEGORY_NEGATE`, `EVENT_CHAINING`, `Duel.IsChainNegatable(ev)`, `Duel.NegateActivation(ev)` |
| "negate the effect" (of an activation) | `CATEGORY_DISABLE`, `Duel.IsChainDisablable(ev)`, `Duel.NegateEffect(ev)` |
| "negate the effects of" a face-up card | `CATEGORY_DISABLE`, `tc:NegateEffects(e:GetHandler(),RESET_PHASE\|PHASE_END)` or `EFFECT_DISABLE`+`EFFECT_DISABLE_EFFECT` |
| "gains X ATK" | `CATEGORY_ATKCHANGE`, `tc:UpdateAttack(X,RESETS_STANDARD_PHASE_END,e:GetHandler())` for "until the end of this turn" |
| "change its battle position" | `CATEGORY_POSITION`, `Duel.ChangePosition` |
| "take control" | `CATEGORY_CONTROL`, `Duel.GetControl` |
| "equip" | `CATEGORY_EQUIP`, `Duel.Equip` + an equip limit |
| "Set" (a Spell/Trap) | `CATEGORY_SET` (newer scripts), `Duel.SSet(tp,g)` |
| "Fusion Summon" | `Fusion.CreateSummonEff{...}` |
| "Ritual Summon" | `Ritual.AddProcGreater{...}` / `Ritual.AddProcEqual{...}` |
| "Normal Summon 1 monster" (by effect) | `CATEGORY_SUMMON`, `Duel.Summon(tp,c,true,nil)` |
| "toss a coin" / "roll a die" | `CATEGORY_COIN` / `CATEGORY_DICE`, `s.toss_coin=true` / `s.roll_dice=true` |
| "you control" / "your opponent controls" / "on the field" | `(tp,LOCATION_X,0)` / `(tp,0,LOCATION_X)` / `(tp,LOCATION_X,LOCATION_X)` in `Duel.*Matching*` calls |
| "face-up" | `c:IsFaceup()` or `aux.FaceupFilter(f,...)`; always check it for monsters "you control" whose properties are inspected |
| "(This card is always treated as a "X" card.)" | Database `setcode` only; no script |
| "This card's name becomes "X" while ..." | `EFFECT_CHANGE_CODE` + `EFFECT_FLAG_SINGLE_RANGE` |
| "Cannot be Normal Summoned/Set." | `c:EnableUnsummonable()` or `c:AddMustBeSpecialSummoned()`; plus `EFFECT_SPSUMMON_CONDITION` if a specific method is required |
| "Must be Special Summoned with/by ..." (Extra Deck, Ritual) | `c:EnableReviveLimit()` + the procedure |
| "You cannot Special Summon monsters, except X, the turn you activate this effect." | Cost-time lock: `Duel.AddCustomActivityCounter` + `EFFECT_CANNOT_SPECIAL_SUMMON` with `EFFECT_FLAG_OATH` (template 14) |
| "... for the rest of this turn after this card resolves" | Register the restriction in the operation, `RESET_PHASE\|PHASE_END` (template 15) |

---

## 9. Worked example

> *Half Slice of Nickeline* (pre-release): "If this card is Special Summoned from the Deck:
> You can add 1 Level 4 or lower Rock monster from your Deck to your hand, except "Half
> Slice of Nickeline". If this card is sent to the GY as Synchro Material, you can (except
> during the Damage Step): Immediately after this effect resolves, Normal Summon 1 Rock
> monster. You can only use each effect of "Half Slice of Nickeline" once per turn."

| # | Kind | Type / code | Condition | OPT | Cost | Target | Resolution |
|---|---|---|---|---|---|---|---|
| 1 | Optional trigger, "If" | `SINGLE+TRIGGER_O`, `EVENT_SPSUMMON_SUCCESS`, `DELAY` | `c:IsSummonLocation(LOCATION_DECK)` | `{id,0}` | – | – | search Level ≤4 Rock, `not IsCode(id)` |
| 2 | Optional trigger, "If ..., you can" | `SINGLE+TRIGGER_O`, `EVENT_BE_MATERIAL`, `DELAY` | in GY, `r==REASON_SYNCHRO`, `not Duel.IsDamageStep()` (SINGLE trigger) | `{id,1}` | – | – | `Duel.Summon` a Rock monster |

Metadata: `s.listed_names={id}` because the text says `except "Half Slice of Nickeline"`.
Strings: `str1`/`str2` hold the two effect texts (`aux.Stringid(id,0)` / `(id,1)`).
The real script is `pre-release/c101402088.lua`.
