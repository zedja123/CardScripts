# 02 · Reading card text (PSCT) and mapping it to Lua

Problem-Solving Card Text (PSCT) is Konami's standardized card-text grammar. Every
punctuation mark and connective has a defined rules meaning, and EDOPro scripts encode
those meanings directly. Reading the text precisely is therefore the first half of
scripting a card.

> **Sources.** The grammar comes from Konami's PSCT article series (Kevin Tewart,
> yugioh-card.com, Parts 2–7, 2011–2012; read from saved copies because this environment
> cannot reach the site). §13 summarises the articles part by part. Every mapping was then
> checked against the official scripts that implement the same wording (the percentages
> are "scripts that use the construct / scripts whose text has the wording"). Where an
> official script behaves differently from the articles, the articles give the rule and
> the difference is noted. The articles use the wording of their time ("Graveyard",
> "Warrior-Type", "Xyz Material"); current texts say "GY", "Warrior", "material", but the
> punctuation and conjunction rules are the ones still printed on cards.

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
4. On a monster, a sentence with a location in **parentheses** and no colon/semicolon
   ("you can Special Summon this card (from your hand)") is a **built-in summon**: a
   summoning procedure, not an effect (§11).
5. On a Continuous Spell/Trap already face-up, a sentence with a colon or semicolon is an
   activated effect of the card on the field (Part 4, "Fusion Gate"), scripted with
   `SetRange(LOCATION_SZONE)`.
6. Pendulum Monsters have two blocks: `[ Pendulum Effect ]` (works in the Pendulum Zone,
   `SetRange(LOCATION_PZONE)`) and `[ Monster Effect ]`.
7. The "once per turn" sentence at the end applies to the effects it names (see §5).

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

What the articles add (Parts 3 and 4):

| Rule | Example | Script |
|---|---|---|
| A **condition** (before the colon) only has to be met **on activation**. If it stops being true before resolution, the effect still resolves. | "Magical Dimension": "If you control a face-up Spellcaster monster: Target 1 monster; ..." | Put it in `SetCondition` only. Do **not** repeat it in `SetOperation`. |
| A requirement that must still hold **on resolution** is written separately. | "Zombie Master": "This card must remain face-up on the field to activate and to resolve this effect." | Check it in the operation too (`c:IsRelateToEffect(e) and c:IsFaceup()`). |
| Paying, discarding, Tributing, destroying or banishing **before the semicolon** is a cost, paid on activation. | "Raigeki Break": "Discard 1 card to target 1 card on the field; destroy it." | `SetCost` |
| "`<cost>`, **then target** ...;" pays the cost first and chooses targets afterwards, both on activation. | "Zombie Master": "You can send 1 Monster Card from your hand to the GY, then target 1 ...;" | `SetCost` + `SetTarget` |
| The same actions **after the semicolon** are not costs; they happen on resolution. | "Black Garden": "...; destroy this card and all face-up Plant monsters, then Special Summon that target." | In `SetOperation` |
| In a chain, all activation parts (before the semicolons) happen when each link is activated; the resolution parts happen afterwards, last link first. | Part 3's Trident Warrior / Raigeki Break / Gemini Spark chain | Engine behaviour (chapter 07 §3) |

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

Part 7 defines the four conjunctions by **timing** (are A and B simultaneous?) and
**causation** (does B need A?):

| Connective | Timing | Causation | Script | Official example |
|---|---|---|---|---|
| "A, **then** B" | B happens **after** A | A is required for B. If A cannot be done, stop. If B cannot be done, A still happens. | `if <A succeeded> then Duel.BreakEffect() <B> end` | "Heraldry Change": Special Summon, `BreakEffect`, then end the Battle Phase |
| "A, **also** B" | Simultaneous | Neither needs the other; do as much as possible | Do A and B independently, no `BreakEffect`; lingering parts ("also, for the rest of this turn ...") are registered whether or not A happened (only 14% of "also" scripts use `BreakEffect`) | "Masked Ninja Ebisu": registers the direct-attack effect before returning cards, with no dependency |
| "A, **and if you do**, B" | Simultaneous | A is required for B, not the reverse | `if <A succeeded> then <B> end`, **no** `Duel.BreakEffect()` (`Duel.SpecialSummon(...)>0`, `Duel.Destroy(...)>0`, `tc:IsLocation(...)` after the move) | "Memory of an Adversary": damage, and banish only if damage was taken |
| "A **and** B" | Simultaneous | **Both** are required: if either cannot be done, do **nothing** | Check that A and B can both be done **before doing either**, then do both, no `BreakEffect` | "Number 53: Heart-eartH": returns before summoning if this card is no longer in the GY to be attached |
| "A, **then you can** B" | As "then", and B is optional | As "then" | `if <A succeeded> and <B possible> and Duel.SelectYesNo(tp,aux.Stringid(id,n)) then Duel.BreakEffect() <B> end` | |
| "A **or** B" / "either ... or ..." | A choice (who chooses and when is stated by the text) | | `Duel.SelectOption` / `Duel.SelectEffect` in the operation | |

Why timing matters: after "A, then B", the **last thing that happened** is B. Optional
"When ...: You can" triggers (no `EFFECT_FLAG_DELAY`) that watch for A's event therefore
miss the timing. With "also", "and if you do" and "and", A's and B's events happen together,
so nothing misses the timing. In the engine, `Duel.BreakEffect()` is what makes the parts
sequential. Leave it out and the events are raised together.

* **Plain "and" is rare on modern cards.** Part 7 notes that most old "and" texts were
  reprinted as "and if you do" (for example "Gemini Spark": "destroy it and draw 1 card",
  whose script draws only if the destruction happened). For new card text, write "and if you
  do" unless all-or-nothing is intended.
* **Several conjunctions in one effect** are applied link by link. "Ignition Beast
  Volcannon": "destroy that target, **also** destroy this card, **then** if both monsters
  were destroyed, inflict damage". Each destruction happens if possible, even if the other
  cannot; the damage follows only if both happened. The official script is stricter: it
  destroys nothing unless both cards are still there.
* **"and" in a built-in summon** ("Quickdraw Synchron": "You can send 1 monster from your
  hand to the GY **and** Special Summon this card (from your hand)"): sending and summoning
  are simultaneous. Do the sending inside the `EFFECT_SPSUMMON_PROC` operation
  (`REASON_COST`), so no separate event comes first; the sent card's "When" effects do not
  miss the timing.
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
| "Cannot be Normal Summoned/Set." / "Must (first) be Special Summoned ..." | See §11: the exact wording decides between `EnableReviveLimit`, `AddMustBeSpecialSummoned` and `EFFECT_SPSUMMON_CONDITION`, and the database type needs `TYPE_SPSUMMON` |
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

---

## 10. Target references on resolution (Parts 4 and 6)

The word the resolution uses for its targets decides what is checked again when it
resolves:

| Resolution wording | Meaning | Script | Official example |
|---|---|---|---|
| "that target", "the targeted ...", "those targets" | Every targeting requirement must still be met; a target that no longer qualifies is not affected | `tc:IsRelateToEffect(e)` **and** the target filter again | "Trap Hole" re-checks face-up and ATK ≥ 1000 |
| "it", "them", "they" | Only that the card is still where it was targeted | `tc:IsRelateToEffect(e)`, plus what the action itself needs (face-up to change ATK or Level) | "Pain Painter": each remaining face-up target becomes Level 2, Zombie or not |
| "both" (or "all") | Every target must still qualify; if one does not, nothing happens | `local g=Duel.GetTargetCards(e)` and return unless every target qualifies | "Blackwing - Hillen the Tengu-wind" returns if either card fails |
| Several targets without "both" | Apply to the targets that are still valid | `Duel.GetTargetCards(e)` and loop | "Pain Painter" |
| A value read "in the GY" ("equal to the ATK of the destroyed monster in the GY") | The card must still be there when the value is read | Check `tc:IsLocation(LOCATION_GRAVE)` before reading it | "Armory Arm" |

Engine note (ygopro-core `card.cpp`, `card::reset`): a target keeps its relation to the
chain link when it is flipped face-down or changes control. The relation is cleared only
when the card moves: to the hand, Deck, GY or banishment, into material, or between the
Monster and Spell/Trap Zones. So `IsRelateToEffect` alone gives the "it" behaviour, and
the "that target" re-checks must be written out. Some official scripts are stricter than
the article on "it" ("Adreus, Keeper of Armageddon" also checks `IsFaceup()`); for new
scripts, follow the article.

---

## 11. Special Summon wording (Part 5)

There are two groups:

* **Effects that Special Summon**: trigger, Ignition, Quick and Flip effects, and
  Spells/Traps. They start a Chain. Cards that "negate the Summon" cannot negate these
  Summons; only the activation or the effect can be negated. Script: `Duel.SpecialSummon`
  in an operation.
* **Built-in Summons**: no colon or semicolon, and the location in parentheses; this group
  also covers Synchro, Xyz, Link, Contact Fusion and Ritual Summons. They do not start a
  Chain, and cards that "negate the Summon" can negate them. Script: a summoning procedure
  (`EFFECT_SPSUMMON_PROC`, `Synchro.AddProcedure`, `Xyz.AddProcedure`, `Link.AddProcedure`,
  `Fusion.AddContactProc`, ...).

| Text | Meaning | Script | Database `type` | Official example |
|---|---|---|---|---|
| "If ..., you can Special Summon this card (from your hand)." | Built-in; the card can also be Normal Summoned and freely revived | `EFFECT_SPSUMMON_PROC` | Ordinary monster type | "Cyber Dragon" |
| "Cannot be Normal Summoned/Set. Must first be Special Summoned (from your hand) by ..." | Built-in; once properly Summoned, other cards can revive it | `c:EnableReviveLimit()` + `EFFECT_SPSUMMON_PROC` | Add `TYPE_SPSUMMON` (0x2000000) | "Ghost Ship", "Dragon Queen of Tragic Endings" |
| "Cannot be Normal Summoned/Set. Must be Special Summoned (from your hand) by ..., and cannot be Special Summoned by other ways." | Only its own procedure, ever | `c:EnableReviveLimit()` + `c:AddMustBeSpecialSummoned()` + `EFFECT_SPSUMMON_PROC` | `TYPE_SPSUMMON` | "Destiny HERO - Dogma" |
| "... cannot be Special Summoned by other ways, except by its own effect." | Only the stated method and its own effect | `c:EnableReviveLimit()` + `EFFECT_SPSUMMON_CONDITION` (no value) + its own Summon with `nocheck=true` (`Duel.SpecialSummon(c,0,tp,tp,true,false,POS_FACEUP)`) | `TYPE_SPSUMMON` | "Vennominaga the Deity of Poisonous Snakes" |
| "Must first be Special Summoned (from your Extra Deck) by returning ... (You do not use "Polymerization".)" | Contact Fusion | `c:EnableReviveLimit()` + `Fusion.AddContactProc` | Fusion type | "Elemental HERO Marine Neos" |

* **"Cannot be Normal Summoned/Set"** is enforced by the database: the core refuses a
  Normal Summon when `type` contains `TYPE_SPSUMMON` (ygopro-core `card::is_summonable_card`).
  `c:EnableUnsummonable()` gives the same result from the script, but official cards use
  the type flag. `lint.py` reports W042 when the text has the sentence and the type lacks
  the flag.
* **"Must first"**: if the built-in Summon is negated, the monster was never properly
  Summoned (no `STATUS_PROC_COMPLETE`), so `EnableReviveLimit` stops it from being revived.
  The same applies to Synchro, Xyz, Link and Contact Fusion Summons.
* Every built-in Summon except Synchro and Xyz Summons states its location in parentheses.
  That is how to recognise a procedure sentence.

---

## 12. Terminology (Parts 2 and 6)

| Wording | Script |
|---|---|
| "banish" (formerly "remove from play") | `Duel.Remove(g,POS_FACEUP,REASON_EFFECT)`, `CATEGORY_REMOVE`; face-down only when the text says so |
| "banished cards" | `LOCATION_REMOVED` (+ `IsFaceup()` when the card must be identified) |
| "leaves the field" (formerly "is removed from the field") | `EVENT_LEAVE_FIELD` (after the move) / `EVENT_LEAVE_FIELD_P` (before). Part 2: these effects do not activate when the card goes to the Deck. The engine enforces this by default: a card's own triggers cannot activate from the Deck or the face-down Extra Deck unless a duel option allows it (ygopro-core `effect.cpp`, `is_activateable`). 17 of 194 official leave-the-field triggers also add `not c:IsLocation(LOCATION_DECK)` for that option |
| "remove" | Only for counters ("Remove 1 Spell Counter"): `RemoveCounter` / `Cost.RemoveCounterFromSelf` |
| "inflict piercing battle damage" | `EFFECT_PIERCE` (single, or field for "monsters you control": "Dragon's Rage") |
| "cannot target ... for attacks" (formerly "select as an attack target") | `EFFECT_CANNOT_SELECT_BATTLE_TARGET` ("Marauding Captain") |
| "HERO" (capitals) | The "HERO" archetype names; spell them exactly as printed |
| "a Spell/Trap **Card** is activated" | Activation of the card itself: `re:IsHasType(EFFECT_TYPE_ACTIVATE)` |
| "a Spell/Trap **effect**" | Effect of a Spell/Trap already on the field: `re:IsSpellTrapEffect() and not re:IsHasType(EFFECT_TYPE_ACTIVATE)` |
| "a Spell/Trap Card or effect" | Either: `re:IsSpellTrapEffect()` |
| "a Spell, Trap, Spell/Trap effect, or Effect Monster's effect" | Any activation; no type filter on `re` ("Stardust Dragon") |
| "cannot activate Spell/Trap Cards" | Card activations only: `EFFECT_CANNOT_ACTIVATE` with value `re:IsHasType(EFFECT_TYPE_ACTIVATE)` ("Vylon Filament"); effects of face-up cards can still be activated |
| "... (during the Chain)" / "immediately" | A continuous effect acting mid-Chain, with no Chain of its own: `EFFECT_TYPE_FIELD+EFFECT_TYPE_CONTINUOUS`, e.g. on `EVENT_CHAIN_SOLVED` ("Bountiful Artemis") |

---

## 13. The PSCT articles, part by part

| Part | Title (date) | Rules used in this chapter |
|---|---|---|
| 2 | New Words & Phrases (2011-05-23) | banish; leaves the field (not to the Deck); piercing battle damage; "target for attacks"; "HERO" → §12 |
| 3 | Conditions, Activations, and Effects (2011-06-01) | CONDITIONS : ACTIVATION ; RESOLUTION; a colon or semicolon means a Chain; monsters without them never start one; Spells/Traps always do; chain building → §1, §2 |
| 4 | The Clues on Your Cards (2011-06-01) | costs on activation; conditions checked only on activation; "that target" vs "it"; "both"; "then target"; Continuous Spells/Traps with colons → §1, §2, §10 |
| 5 | Special Summons (2011-07-27) | effects that Summon vs built-in Summons; parentheses; "must first"; negating Summons → §11 |
| 6 | Finding Clues in TU6 & GENF (2011-08-08) | Spell/Trap Card vs effect; "and" in built-in Summons; references "in the GY"; "targeted" vs "they"; continuous effects "during the Chain" → §6, §10, §12 |
| 7 | 2012 Update: Conjunction Functions (2012-12-12) | then / also / and if you do / and: timing and causation; several conjunctions in one effect → §6 |

Part 1 (the introduction) was not among the saved copies; the later parts refer to it only
as background.
