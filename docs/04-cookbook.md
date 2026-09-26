# 04 · Pattern cookbook

Complete, tested scripts for the patterns that cover most cards. Every template below is
generated from `.claude/skills/edopro-card-scripting/templates/` and is verified to load in
the real core and to pass the linter (`tools/build_cookbook.py --check`).

How to use a template:

1. Find the closest template here **and** the closest real cards with
   `cdb.py analogs <card>`; prefer the real card when it matches the wording exactly.
2. Replace the placeholders: `SET_ARCHETYPE` with the real `SET_` constant, `"Archetype"`
   and `"Template"` in comments with the real names.
3. Keep the effect comment identical to the database string of that effect.

Placeholders are not real constants; the templates only load when `SET_ARCHETYPE` is
defined (the checker defines it as a test value).

## Index

- [01 · Trigger on summon, search](#01-trigger-on-summon-search)
- [02 · Ignition, Special Summon itself from the hand with a cost](#02-ignition-selfsummon-from-hand)
- [03 · Quick Effect from the hand, negate the activation](#03-quick-negate-activation-handtrap)
- [04 · Quick Effect on the field, target and destroy](#04-quick-target-destroy)
- [05 · Trigger when sent to the GY, target a card in the GY](#05-trigger-sent-to-gy-target-gy)
- [06 · Continuous effects (stat change, protection, immunity)](#06-continuous-stat-and-protection)
- [07 · Normal Spell, "You can only activate 1 per turn"](#07-normal-spell-oath-search)
- [08 · Normal Trap, target and negate effects until the end of the turn](#08-normal-trap-target-negate)
- [09 · Continuous Spell/Trap with an activation and an effect on the field](#09-continuous-spell-trap)
- [10 · Field Spell](#10-field-spell)
- [11 · Equip Spell](#11-equip-spell)
- [12 · "Activate 1 of these effects" (choice made on activation)](#12-choose-one-effect)
- [13 · Inherent Special Summon procedure (does not start a Chain)](#13-inherent-special-summon)
- [14 · Summon restriction tied to activation ("the turn you activate this effect")](#14-lock-the-turn-you-activate)
- [15 · Lingering player effect applied on resolution ("for the rest of this turn")](#15-lingering-rest-of-turn)
- [16 · Fusion Monster](#16-fusion-monster)
- [17 · Synchro Monster](#17-synchro-monster)
- [18 · Xyz Monster with a detach cost](#18-xyz-monster-detach)
- [19 · Link Monster](#19-link-monster)
- [20 · Fusion Spell](#20-fusion-spell)
- [21 · Ritual Spell (the Ritual Monster itself only needs c:EnableReviveLimit())](#21-ritual-spell-and-monster)
- [22 · Pendulum Monster with a Pendulum Effect](#22-pendulum-monster)
- [23 · FLIP effect](#23-flip-effect)
- [24 · Token summon](#24-token-summon)
- [25 · Destruction replacement from the GY](#25-destroy-replacement)
- [26 · Trigger when this card destroys a monster by battle](#26-battle-destroying-trigger)
- [27 · Trigger when this card leaves the field because of the opponent](#27-leaves-field-by-opponent)
- [28 · Banish until a later phase](#28-temporary-banish)
- [29 · Mandatory trigger during the End Phase](#29-mandatory-end-phase)
- [30 · Counters (permit, place on activation of Spells, remove as cost)](#30-counters)
- [31 · Cannot be Normal Summoned/Set, special summon condition](#31-summon-condition-nomi)
- [32 · Resolution conjunctions ("and if you do", "then", "also")](#32-conjunctions)

---

<a id="01-trigger-on-summon-search"></a>
## 01 · Trigger on summon, search

> If this card is Normal or Special Summoned: You can add 1 "Archetype" monster from your Deck to your hand, except "Template". You can only use this effect of "Template" once per turn.

- The two clones share SetCountLimit(1,id): one counter for 'this effect'.
- EFFECT_FLAG_DELAY because the text says 'If' (cannot miss the timing).
- listed_names contains id because the text says except its own name.

Source: `templates/01_trigger_on_summon_search.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--If this card is Normal or Special Summoned: You can add 1 "Archetype" monster from your Deck to your hand, except "Template"
	local e1a=Effect.CreateEffect(c)
	e1a:SetDescription(aux.Stringid(id,0))
	e1a:SetCategory(CATEGORY_TOHAND+CATEGORY_SEARCH)
	e1a:SetType(EFFECT_TYPE_SINGLE+EFFECT_TYPE_TRIGGER_O)
	e1a:SetProperty(EFFECT_FLAG_DELAY)
	e1a:SetCode(EVENT_SUMMON_SUCCESS)
	e1a:SetCountLimit(1,id)
	e1a:SetTarget(s.thtg)
	e1a:SetOperation(s.thop)
	c:RegisterEffect(e1a)
	local e1b=e1a:Clone()
	e1b:SetCode(EVENT_SPSUMMON_SUCCESS)
	c:RegisterEffect(e1b)
end
s.listed_names={id}
s.listed_series={SET_ARCHETYPE}
function s.thfilter(c)
	return c:IsSetCard(SET_ARCHETYPE) and c:IsMonster() and not c:IsCode(id) and c:IsAbleToHand()
end
function s.thtg(e,tp,eg,ep,ev,re,r,rp,chk)
	if chk==0 then return Duel.IsExistingMatchingCard(s.thfilter,tp,LOCATION_DECK,0,1,nil) end
	Duel.SetOperationInfo(0,CATEGORY_TOHAND,nil,1,tp,LOCATION_DECK)
end
function s.thop(e,tp,eg,ep,ev,re,r,rp)
	Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_ATOHAND)
	local g=Duel.SelectMatchingCard(tp,s.thfilter,tp,LOCATION_DECK,0,1,1,nil)
	if #g>0 then
		Duel.SendtoHand(g,nil,REASON_EFFECT)
		Duel.ConfirmCards(1-tp,g)
	end
end
```

---

<a id="02-ignition-selfsummon-from-hand"></a>
## 02 · Ignition, Special Summon itself from the hand with a cost

> You can discard 1 other card; Special Summon this card from your hand. You can only use this effect of "Template" once per turn.

- Cost.Discard(nil,true): any card, excluding this one (the 'other' flag).
- The zone check lives in the target (chk==0); the operation re-checks the relation.

Source: `templates/02_ignition_selfsummon_from_hand.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--You can discard 1 other card; Special Summon this card from your hand
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_SPECIAL_SUMMON)
	e1:SetType(EFFECT_TYPE_IGNITION)
	e1:SetRange(LOCATION_HAND)
	e1:SetCountLimit(1,id)
	e1:SetCost(Cost.Discard(nil,true))
	e1:SetTarget(s.sptg)
	e1:SetOperation(s.spop)
	c:RegisterEffect(e1)
end
function s.sptg(e,tp,eg,ep,ev,re,r,rp,chk)
	local c=e:GetHandler()
	if chk==0 then return Duel.GetLocationCount(tp,LOCATION_MZONE)>0
		and c:IsCanBeSpecialSummoned(e,0,tp,false,false) end
	Duel.SetOperationInfo(0,CATEGORY_SPECIAL_SUMMON,c,1,tp,0)
end
function s.spop(e,tp,eg,ep,ev,re,r,rp)
	local c=e:GetHandler()
	if c:IsRelateToEffect(e) then
		Duel.SpecialSummon(c,0,tp,tp,false,false,POS_FACEUP)
	end
end
```

---

<a id="03-quick-negate-activation-handtrap"></a>
## 03 · Quick Effect from the hand, negate the activation

> When your opponent activates a card or effect (Quick Effect): You can discard this card; negate the activation, and if you do, destroy that card. You can only use this effect of "Template" once per turn.

- EVENT_CHAINING: eg = the activated card, ev = its chain link, re = the effect, rp = its player.
- DAMAGE_STEP+DAMAGE_CAL flags: chain responses are usually legal in the Damage Step.
- Destroy only if the card is still related to its own effect (it may have left the field).

Source: `templates/03_quick_negate_activation_handtrap.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--When your opponent activates a card or effect (Quick Effect): You can discard this card; negate the activation, and if you do, destroy that card
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_NEGATE+CATEGORY_DESTROY)
	e1:SetType(EFFECT_TYPE_QUICK_O)
	e1:SetProperty(EFFECT_FLAG_DAMAGE_STEP+EFFECT_FLAG_DAMAGE_CAL)
	e1:SetCode(EVENT_CHAINING)
	e1:SetRange(LOCATION_HAND)
	e1:SetCountLimit(1,id)
	e1:SetCondition(function(e,tp,eg,ep,ev,re,r,rp)
		return rp==1-tp and Duel.IsChainNegatable(ev)
	end)
	e1:SetCost(Cost.SelfDiscard)
	e1:SetTarget(s.negtg)
	e1:SetOperation(s.negop)
	c:RegisterEffect(e1)
end
function s.negtg(e,tp,eg,ep,ev,re,r,rp,chk)
	if chk==0 then return true end
	local rc=re:GetHandler()
	Duel.SetOperationInfo(0,CATEGORY_NEGATE,eg,1,0,0)
	if rc:IsDestructable() and rc:IsRelateToEffect(re) then
		Duel.SetOperationInfo(0,CATEGORY_DESTROY,eg,1,0,0)
	end
end
function s.negop(e,tp,eg,ep,ev,re,r,rp)
	if Duel.NegateActivation(ev) and re:GetHandler():IsRelateToEffect(re) then
		Duel.Destroy(eg,REASON_EFFECT)
	end
end
```

---

<a id="04-quick-target-destroy"></a>
## 04 · Quick Effect on the field, target and destroy

> (Quick Effect): You can target 1 card your opponent controls; destroy it. You can only use this effect of "Template" once per turn.

- The chkc line repeats the target conditions for target redirection.
- Hint timing lets the client offer the effect at common response windows.

Source: `templates/04_quick_target_destroy.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--(Quick Effect): You can target 1 card your opponent controls; destroy it
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_DESTROY)
	e1:SetType(EFFECT_TYPE_QUICK_O)
	e1:SetProperty(EFFECT_FLAG_CARD_TARGET)
	e1:SetCode(EVENT_FREE_CHAIN)
	e1:SetRange(LOCATION_MZONE)
	e1:SetCountLimit(1,id)
	e1:SetHintTiming(0,TIMING_STANDBY_PHASE|TIMING_MAIN_END|TIMINGS_CHECK_MONSTER_E)
	e1:SetTarget(s.destg)
	e1:SetOperation(s.desop)
	c:RegisterEffect(e1)
end
function s.destg(e,tp,eg,ep,ev,re,r,rp,chk,chkc)
	if chkc then return chkc:IsOnField() and chkc:IsControler(1-tp) end
	if chk==0 then return Duel.IsExistingTarget(nil,tp,0,LOCATION_ONFIELD,1,nil) end
	Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_DESTROY)
	local g=Duel.SelectTarget(tp,nil,tp,0,LOCATION_ONFIELD,1,1,nil)
	Duel.SetOperationInfo(0,CATEGORY_DESTROY,g,1,0,0)
end
function s.desop(e,tp,eg,ep,ev,re,r,rp)
	local tc=Duel.GetFirstTarget()
	if tc:IsRelateToEffect(e) then
		Duel.Destroy(tc,REASON_EFFECT)
	end
end
```

---

<a id="05-trigger-sent-to-gy-target-gy"></a>
## 05 · Trigger when sent to the GY, target a card in the GY

> If this card is sent to the GY: You can target 1 "Archetype" Spell in your GY; add it to your hand. You can only use this effect of "Template" once per turn.

- Targeting in the GY: no aux.NecroValleyFilter needed; use it for non-targeted GY selections in the operation.

Source: `templates/05_trigger_sent_to_gy_target_gy.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--If this card is sent to the GY: You can target 1 "Archetype" Spell in your GY; add it to your hand
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_TOHAND)
	e1:SetType(EFFECT_TYPE_SINGLE+EFFECT_TYPE_TRIGGER_O)
	e1:SetProperty(EFFECT_FLAG_DELAY+EFFECT_FLAG_CARD_TARGET)
	e1:SetCode(EVENT_TO_GRAVE)
	e1:SetCountLimit(1,id)
	e1:SetTarget(s.thtg)
	e1:SetOperation(s.thop)
	c:RegisterEffect(e1)
end
s.listed_series={SET_ARCHETYPE}
function s.thfilter(c)
	return c:IsSetCard(SET_ARCHETYPE) and c:IsSpell() and c:IsAbleToHand()
end
function s.thtg(e,tp,eg,ep,ev,re,r,rp,chk,chkc)
	if chkc then return chkc:IsLocation(LOCATION_GRAVE) and chkc:IsControler(tp) and s.thfilter(chkc) end
	if chk==0 then return Duel.IsExistingTarget(s.thfilter,tp,LOCATION_GRAVE,0,1,nil) end
	Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_ATOHAND)
	local g=Duel.SelectTarget(tp,s.thfilter,tp,LOCATION_GRAVE,0,1,1,nil)
	Duel.SetOperationInfo(0,CATEGORY_TOHAND,g,1,tp,0)
end
function s.thop(e,tp,eg,ep,ev,re,r,rp)
	local tc=Duel.GetFirstTarget()
	if tc:IsRelateToEffect(e) then
		Duel.SendtoHand(tc,nil,REASON_EFFECT)
	end
end
```

---

<a id="06-continuous-stat-and-protection"></a>
## 06 · Continuous effects (stat change, protection, immunity)

> "Archetype" monsters you control gain 500 ATK. Monsters your opponent controls lose 300 ATK. This card cannot be destroyed by card effects. Your opponent cannot target this card with card effects. Unaffected by your opponent's card effects.

- Continuous effects have no description, no count limit and are not activated.
- SINGLE effects that work only on the field need EFFECT_FLAG_SINGLE_RANGE + SetRange.
- aux.tgoval = 'your opponent cannot target'; immunity compares effect owners.

Source: `templates/06_continuous_stat_and_protection.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--"Archetype" monsters you control gain 500 ATK
	local e1=Effect.CreateEffect(c)
	e1:SetType(EFFECT_TYPE_FIELD)
	e1:SetCode(EFFECT_UPDATE_ATTACK)
	e1:SetRange(LOCATION_MZONE)
	e1:SetTargetRange(LOCATION_MZONE,0)
	e1:SetTarget(aux.TargetBoolFunction(Card.IsSetCard,SET_ARCHETYPE))
	e1:SetValue(500)
	c:RegisterEffect(e1)
	--Monsters your opponent controls lose 300 ATK
	local e2=Effect.CreateEffect(c)
	e2:SetType(EFFECT_TYPE_FIELD)
	e2:SetCode(EFFECT_UPDATE_ATTACK)
	e2:SetRange(LOCATION_MZONE)
	e2:SetTargetRange(0,LOCATION_MZONE)
	e2:SetValue(-300)
	c:RegisterEffect(e2)
	--This card cannot be destroyed by card effects
	local e3=Effect.CreateEffect(c)
	e3:SetType(EFFECT_TYPE_SINGLE)
	e3:SetProperty(EFFECT_FLAG_SINGLE_RANGE)
	e3:SetCode(EFFECT_INDESTRUCTABLE_EFFECT)
	e3:SetRange(LOCATION_MZONE)
	e3:SetValue(1)
	c:RegisterEffect(e3)
	--Your opponent cannot target this card with card effects
	local e4=Effect.CreateEffect(c)
	e4:SetType(EFFECT_TYPE_SINGLE)
	e4:SetProperty(EFFECT_FLAG_SINGLE_RANGE)
	e4:SetCode(EFFECT_CANNOT_BE_EFFECT_TARGET)
	e4:SetRange(LOCATION_MZONE)
	e4:SetValue(aux.tgoval)
	c:RegisterEffect(e4)
	--Unaffected by your opponent's card effects
	local e5=Effect.CreateEffect(c)
	e5:SetType(EFFECT_TYPE_SINGLE)
	e5:SetProperty(EFFECT_FLAG_SINGLE_RANGE)
	e5:SetCode(EFFECT_IMMUNE_EFFECT)
	e5:SetRange(LOCATION_MZONE)
	e5:SetValue(function(e,re) return e:GetOwnerPlayer()~=re:GetOwnerPlayer() end)
	c:RegisterEffect(e5)
end
s.listed_series={SET_ARCHETYPE}
```

---

<a id="07-normal-spell-oath-search"></a>
## 07 · Normal Spell, "You can only activate 1 per turn"

> Add 1 "Archetype" monster from your Deck to your hand. You can only activate 1 "Template" per turn.

- EFFECT_COUNT_CODE_OATH: a negated activation does not consume the use.

Source: `templates/07_normal_spell_oath_search.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--Add 1 "Archetype" monster from your Deck to your hand
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_TOHAND+CATEGORY_SEARCH)
	e1:SetType(EFFECT_TYPE_ACTIVATE)
	e1:SetCode(EVENT_FREE_CHAIN)
	e1:SetCountLimit(1,id,EFFECT_COUNT_CODE_OATH)
	e1:SetTarget(s.target)
	e1:SetOperation(s.activate)
	c:RegisterEffect(e1)
end
s.listed_series={SET_ARCHETYPE}
function s.thfilter(c)
	return c:IsSetCard(SET_ARCHETYPE) and c:IsMonster() and c:IsAbleToHand()
end
function s.target(e,tp,eg,ep,ev,re,r,rp,chk)
	if chk==0 then return Duel.IsExistingMatchingCard(s.thfilter,tp,LOCATION_DECK,0,1,nil) end
	Duel.SetOperationInfo(0,CATEGORY_TOHAND,nil,1,tp,LOCATION_DECK)
end
function s.activate(e,tp,eg,ep,ev,re,r,rp)
	Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_ATOHAND)
	local g=Duel.SelectMatchingCard(tp,s.thfilter,tp,LOCATION_DECK,0,1,1,nil)
	if #g>0 then
		Duel.SendtoHand(g,nil,REASON_EFFECT)
		Duel.ConfirmCards(1-tp,g)
	end
end
```

---

<a id="08-normal-trap-target-negate"></a>
## 08 · Normal Trap, target and negate effects until the end of the turn

> Target 1 face-up monster your opponent controls; negate its effects until the end of this turn.

- Card.NegateEffects(tc,rc,reset) applies EFFECT_DISABLE (+ EFFECT_DISABLE_TRAPMONSTER when needed).
- IsNegatableMonster filters face-up monsters whose effects are not already negated.

Source: `templates/08_normal_trap_target_negate.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--Target 1 face-up monster your opponent controls; negate its effects until the end of this turn
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_DISABLE)
	e1:SetType(EFFECT_TYPE_ACTIVATE)
	e1:SetProperty(EFFECT_FLAG_CARD_TARGET)
	e1:SetCode(EVENT_FREE_CHAIN)
	e1:SetHintTiming(0,TIMINGS_CHECK_MONSTER_E)
	e1:SetTarget(s.target)
	e1:SetOperation(s.activate)
	c:RegisterEffect(e1)
end
function s.target(e,tp,eg,ep,ev,re,r,rp,chk,chkc)
	if chkc then return chkc:IsLocation(LOCATION_MZONE) and chkc:IsControler(1-tp) and chkc:IsNegatableMonster() end
	if chk==0 then return Duel.IsExistingTarget(Card.IsNegatableMonster,tp,0,LOCATION_MZONE,1,nil) end
	Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_NEGATE)
	local g=Duel.SelectTarget(tp,Card.IsNegatableMonster,tp,0,LOCATION_MZONE,1,1,nil)
	Duel.SetOperationInfo(0,CATEGORY_DISABLE,g,1,0,0)
end
function s.activate(e,tp,eg,ep,ev,re,r,rp)
	local tc=Duel.GetFirstTarget()
	if tc:IsRelateToEffect(e) and tc:IsFaceup() and not tc:IsDisabled() then
		tc:NegateEffects(e:GetHandler(),RESET_PHASE|PHASE_END)
	end
end
```

---

<a id="09-continuous-spell-trap"></a>
## 09 · Continuous Spell/Trap with an activation and an effect on the field

> Once per turn: You can send 1 "Archetype" card from your Deck to the GY.

- e0 is the bare activation: no description, no target, no operation.
- Effects that work on the field use SetRange(LOCATION_SZONE).

Source: `templates/09_continuous_spell_trap.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--Activate
	local e0=Effect.CreateEffect(c)
	e0:SetType(EFFECT_TYPE_ACTIVATE)
	e0:SetCode(EVENT_FREE_CHAIN)
	c:RegisterEffect(e0)
	--Once per turn: You can send 1 "Archetype" card from your Deck to the GY
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_TOGRAVE)
	e1:SetType(EFFECT_TYPE_IGNITION)
	e1:SetRange(LOCATION_SZONE)
	e1:SetCountLimit(1)
	e1:SetTarget(s.tgtg)
	e1:SetOperation(s.tgop)
	c:RegisterEffect(e1)
end
s.listed_series={SET_ARCHETYPE}
function s.tgfilter(c)
	return c:IsSetCard(SET_ARCHETYPE) and c:IsAbleToGrave()
end
function s.tgtg(e,tp,eg,ep,ev,re,r,rp,chk)
	if chk==0 then return Duel.IsExistingMatchingCard(s.tgfilter,tp,LOCATION_DECK,0,1,nil) end
	Duel.SetOperationInfo(0,CATEGORY_TOGRAVE,nil,1,tp,LOCATION_DECK)
end
function s.tgop(e,tp,eg,ep,ev,re,r,rp)
	Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_TOGRAVE)
	local g=Duel.SelectMatchingCard(tp,s.tgfilter,tp,LOCATION_DECK,0,1,1,nil)
	if #g>0 then
		Duel.SendtoGrave(g,REASON_EFFECT)
	end
end
```

---

<a id="10-field-spell"></a>
## 10 · Field Spell

> All "Archetype" monsters on the field gain 300 ATK/DEF. Once per turn, during your End Phase: You can target 1 "Archetype" monster in your GY; add it to your hand.

- Field Spell effects use SetRange(LOCATION_FZONE).
- 'during your End Phase' = EVENT_PHASE+PHASE_END plus a turn-player condition.

Source: `templates/10_field_spell.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--Activate
	local e0=Effect.CreateEffect(c)
	e0:SetType(EFFECT_TYPE_ACTIVATE)
	e0:SetCode(EVENT_FREE_CHAIN)
	c:RegisterEffect(e0)
	--All "Archetype" monsters on the field gain 300 ATK/DEF
	local e1a=Effect.CreateEffect(c)
	e1a:SetType(EFFECT_TYPE_FIELD)
	e1a:SetCode(EFFECT_UPDATE_ATTACK)
	e1a:SetRange(LOCATION_FZONE)
	e1a:SetTargetRange(LOCATION_MZONE,LOCATION_MZONE)
	e1a:SetTarget(aux.TargetBoolFunction(Card.IsSetCard,SET_ARCHETYPE))
	e1a:SetValue(300)
	c:RegisterEffect(e1a)
	local e1b=e1a:Clone()
	e1b:SetCode(EFFECT_UPDATE_DEFENSE)
	c:RegisterEffect(e1b)
	--Once per turn, during your End Phase: You can target 1 "Archetype" monster in your GY; add it to your hand
	local e2=Effect.CreateEffect(c)
	e2:SetDescription(aux.Stringid(id,0))
	e2:SetCategory(CATEGORY_TOHAND)
	e2:SetType(EFFECT_TYPE_FIELD+EFFECT_TYPE_TRIGGER_O)
	e2:SetProperty(EFFECT_FLAG_CARD_TARGET)
	e2:SetCode(EVENT_PHASE+PHASE_END)
	e2:SetRange(LOCATION_FZONE)
	e2:SetCountLimit(1)
	e2:SetCondition(function(e,tp) return Duel.IsTurnPlayer(tp) end)
	e2:SetTarget(s.thtg)
	e2:SetOperation(s.thop)
	c:RegisterEffect(e2)
end
s.listed_series={SET_ARCHETYPE}
function s.thfilter(c)
	return c:IsSetCard(SET_ARCHETYPE) and c:IsMonster() and c:IsAbleToHand()
end
function s.thtg(e,tp,eg,ep,ev,re,r,rp,chk,chkc)
	if chkc then return chkc:IsLocation(LOCATION_GRAVE) and chkc:IsControler(tp) and s.thfilter(chkc) end
	if chk==0 then return Duel.IsExistingTarget(s.thfilter,tp,LOCATION_GRAVE,0,1,nil) end
	Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_ATOHAND)
	local g=Duel.SelectTarget(tp,s.thfilter,tp,LOCATION_GRAVE,0,1,1,nil)
	Duel.SetOperationInfo(0,CATEGORY_TOHAND,g,1,tp,0)
end
function s.thop(e,tp,eg,ep,ev,re,r,rp)
	local tc=Duel.GetFirstTarget()
	if tc:IsRelateToEffect(e) then
		Duel.SendtoHand(tc,nil,REASON_EFFECT)
	end
end
```

---

<a id="11-equip-spell"></a>
## 11 · Equip Spell

> Equip only to a Warrior monster. It gains 700 ATK. If the equipped monster destroys an opponent's monster by battle: You can draw 1 card.

- aux.AddEquipProcedure registers the activation, targeting and equip limit.
- EFFECT_TYPE_EQUIP effects apply to the equipped monster.

Source: `templates/11_equip_spell.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--Equip only to a Warrior monster
	aux.AddEquipProcedure(c,nil,aux.FilterBoolFunction(Card.IsRace,RACE_WARRIOR))
	--It gains 700 ATK
	local e1=Effect.CreateEffect(c)
	e1:SetType(EFFECT_TYPE_EQUIP)
	e1:SetCode(EFFECT_UPDATE_ATTACK)
	e1:SetValue(700)
	c:RegisterEffect(e1)
	--If the equipped monster destroys an opponent's monster by battle: You can draw 1 card
	local e2=Effect.CreateEffect(c)
	e2:SetDescription(aux.Stringid(id,0))
	e2:SetCategory(CATEGORY_DRAW)
	e2:SetType(EFFECT_TYPE_FIELD+EFFECT_TYPE_TRIGGER_O)
	e2:SetProperty(EFFECT_FLAG_PLAYER_TARGET)
	e2:SetCode(EVENT_BATTLE_DESTROYING)
	e2:SetRange(LOCATION_SZONE)
	e2:SetCondition(function(e,tp,eg)
		local ec=e:GetHandler():GetEquipTarget()
		return ec and eg:IsContains(ec) and ec:IsStatus(STATUS_OPPO_BATTLE)
	end)
	e2:SetTarget(s.drtg)
	e2:SetOperation(s.drop)
	c:RegisterEffect(e2)
end
function s.drtg(e,tp,eg,ep,ev,re,r,rp,chk)
	if chk==0 then return Duel.IsPlayerCanDraw(tp,1) end
	Duel.SetTargetPlayer(tp)
	Duel.SetTargetParam(1)
	Duel.SetOperationInfo(0,CATEGORY_DRAW,nil,0,tp,1)
end
function s.drop(e,tp,eg,ep,ev,re,r,rp)
	local p,d=Duel.GetChainInfo(0,CHAININFO_TARGET_PLAYER,CHAININFO_TARGET_PARAM)
	Duel.Draw(p,d,REASON_EFFECT)
end
```

---

<a id="12-choose-one-effect"></a>
## 12 · "Activate 1 of these effects" (choice made on activation)

> Activate 1 of these effects; ● Draw 1 card. ● Special Summon 1 "Archetype" monster from your hand. You can only activate 1 "Template" per turn.

- The choice is made on activation (target function) because the text says 'Activate 1 of these effects'.
- The category is set per choice so that cards like Ash Blossom see the right one.
- e:GetChainData().choice is the newer alternative to SetLabel.

Source: `templates/12_choose_one_effect.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--Activate 1 of these effects
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetType(EFFECT_TYPE_ACTIVATE)
	e1:SetCode(EVENT_FREE_CHAIN)
	e1:SetCountLimit(1,id,EFFECT_COUNT_CODE_OATH)
	e1:SetTarget(s.efftg)
	e1:SetOperation(s.effop)
	c:RegisterEffect(e1)
end
s.listed_series={SET_ARCHETYPE}
function s.spfilter(c,e,tp)
	return c:IsSetCard(SET_ARCHETYPE) and c:IsCanBeSpecialSummoned(e,0,tp,false,false)
end
function s.efftg(e,tp,eg,ep,ev,re,r,rp,chk)
	--● Draw 1 card
	local b1=Duel.IsPlayerCanDraw(tp,1)
	--● Special Summon 1 "Archetype" monster from your hand
	local b2=Duel.GetLocationCount(tp,LOCATION_MZONE)>0
		and Duel.IsExistingMatchingCard(s.spfilter,tp,LOCATION_HAND,0,1,nil,e,tp)
	if chk==0 then return b1 or b2 end
	local op=Duel.SelectEffect(tp,
		{b1,aux.Stringid(id,1)},
		{b2,aux.Stringid(id,2)})
	e:SetLabel(op)
	if op==1 then
		e:SetCategory(CATEGORY_DRAW)
		Duel.SetOperationInfo(0,CATEGORY_DRAW,nil,0,tp,1)
	elseif op==2 then
		e:SetCategory(CATEGORY_SPECIAL_SUMMON)
		Duel.SetOperationInfo(0,CATEGORY_SPECIAL_SUMMON,nil,1,tp,LOCATION_HAND)
	end
end
function s.effop(e,tp,eg,ep,ev,re,r,rp)
	local op=e:GetLabel()
	if op==1 then
		--● Draw 1 card
		Duel.Draw(tp,1,REASON_EFFECT)
	elseif op==2 then
		--● Special Summon 1 "Archetype" monster from your hand
		if Duel.GetLocationCount(tp,LOCATION_MZONE)<=0 then return end
		Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_SPSUMMON)
		local g=Duel.SelectMatchingCard(tp,s.spfilter,tp,LOCATION_HAND,0,1,1,nil,e,tp)
		if #g>0 then
			Duel.SpecialSummon(g,0,tp,tp,false,false,POS_FACEUP)
		end
	end
end
```

---

<a id="13-inherent-special-summon"></a>
## 13 · Inherent Special Summon procedure (does not start a Chain)

> If you control an "Archetype" monster, you can Special Summon this card (from your hand). You can only Special Summon "Template" once per turn this way.

- Inherent summons do not use the Chain; condition(e,c) with c==nil means 'is the procedure available'.
- 'once per turn this way' = SetCountLimit(1,id,EFFECT_COUNT_CODE_OATH) on the procedure.

Source: `templates/13_inherent_special_summon.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--If you control an "Archetype" monster, you can Special Summon this card (from your hand)
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetType(EFFECT_TYPE_FIELD)
	e1:SetProperty(EFFECT_FLAG_UNCOPYABLE)
	e1:SetCode(EFFECT_SPSUMMON_PROC)
	e1:SetRange(LOCATION_HAND)
	e1:SetCountLimit(1,id,EFFECT_COUNT_CODE_OATH)
	e1:SetCondition(s.spcon)
	c:RegisterEffect(e1)
end
s.listed_series={SET_ARCHETYPE}
function s.spcon(e,c)
	if c==nil then return true end
	local tp=c:GetControler()
	return Duel.GetLocationCount(tp,LOCATION_MZONE)>0
		and Duel.IsExistingMatchingCard(aux.FaceupFilter(Card.IsSetCard,SET_ARCHETYPE),tp,LOCATION_MZONE,0,1,nil)
end
```

---

<a id="14-lock-the-turn-you-activate"></a>
## 14 · Summon restriction tied to activation ("the turn you activate this effect")

> You can Tribute this card; Special Summon 1 "Archetype" monster from your Deck. You cannot Special Summon monsters from the Extra Deck, except "Archetype" monsters, the turn you activate this effect. You can only use this effect of "Template" once per turn.

- The lock is created in the cost with EFFECT_FLAG_OATH so that it disappears if the activation is negated.
- The activity counter makes the effect unusable if a forbidden summon already happened this turn.
- aux.addTempLizardCheck informs 'Clock Lizard'-type effects of the Extra Deck restriction.
- GetMZoneCount(tp,c) because Tributing this card frees its zone.

Source: `templates/14_lock_the_turn_you_activate.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--You can Tribute this card; Special Summon 1 "Archetype" monster from your Deck
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_SPECIAL_SUMMON)
	e1:SetType(EFFECT_TYPE_IGNITION)
	e1:SetRange(LOCATION_MZONE)
	e1:SetCountLimit(1,id)
	e1:SetCost(s.spcost)
	e1:SetTarget(s.sptg)
	e1:SetOperation(s.spop)
	c:RegisterEffect(e1)
	--Track Special Summons from the Extra Deck of non-"Archetype" monsters
	Duel.AddCustomActivityCounter(id,ACTIVITY_SPSUMMON,function(c) return not c:IsSummonLocation(LOCATION_EXTRA) or c:IsSetCard(SET_ARCHETYPE) end)
end
s.listed_series={SET_ARCHETYPE}
function s.spcost(e,tp,eg,ep,ev,re,r,rp,chk)
	local c=e:GetHandler()
	if chk==0 then return c:IsReleasable() and Duel.GetCustomActivityCount(id,tp,ACTIVITY_SPSUMMON)==0 end
	Duel.Release(c,REASON_COST)
	--You cannot Special Summon monsters from the Extra Deck, except "Archetype" monsters, the turn you activate this effect
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,1))
	e1:SetType(EFFECT_TYPE_FIELD)
	e1:SetProperty(EFFECT_FLAG_PLAYER_TARGET+EFFECT_FLAG_OATH+EFFECT_FLAG_CLIENT_HINT)
	e1:SetCode(EFFECT_CANNOT_SPECIAL_SUMMON)
	e1:SetTargetRange(1,0)
	e1:SetTarget(function(e,c) return c:IsLocation(LOCATION_EXTRA) and not c:IsSetCard(SET_ARCHETYPE) end)
	e1:SetReset(RESET_PHASE|PHASE_END)
	Duel.RegisterEffect(e1,tp)
	--"Clock Lizard" check
	aux.addTempLizardCheck(c,tp,function(e,c) return not c:IsOriginalSetCard(SET_ARCHETYPE) end)
end
function s.spfilter(c,e,tp)
	return c:IsSetCard(SET_ARCHETYPE) and c:IsCanBeSpecialSummoned(e,0,tp,false,false)
end
function s.sptg(e,tp,eg,ep,ev,re,r,rp,chk)
	if chk==0 then return Duel.GetMZoneCount(tp,e:GetHandler())>0
		and Duel.IsExistingMatchingCard(s.spfilter,tp,LOCATION_DECK,0,1,nil,e,tp) end
	Duel.SetOperationInfo(0,CATEGORY_SPECIAL_SUMMON,nil,1,tp,LOCATION_DECK)
end
function s.spop(e,tp,eg,ep,ev,re,r,rp)
	if Duel.GetLocationCount(tp,LOCATION_MZONE)<=0 then return end
	Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_SPSUMMON)
	local g=Duel.SelectMatchingCard(tp,s.spfilter,tp,LOCATION_DECK,0,1,1,nil,e,tp)
	if #g>0 then
		Duel.SpecialSummon(g,0,tp,tp,false,false,POS_FACEUP)
	end
end
```

---

<a id="15-lingering-rest-of-turn"></a>
## 15 · Lingering player effect applied on resolution ("for the rest of this turn")

> Draw 2 cards, also for the rest of this turn, you cannot activate monster effects, except "Archetype" monsters'.

- Lingering player effects are registered on resolution with RESET_PHASE|PHASE_END.
- EFFECT_FLAG_CLIENT_HINT + description shows the restriction to the player.

Source: `templates/15_lingering_rest_of_turn.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--Draw 2 cards, also for the rest of this turn, you cannot activate monster effects, except "Archetype" monsters'
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_DRAW)
	e1:SetType(EFFECT_TYPE_ACTIVATE)
	e1:SetProperty(EFFECT_FLAG_PLAYER_TARGET)
	e1:SetCode(EVENT_FREE_CHAIN)
	e1:SetTarget(s.target)
	e1:SetOperation(s.activate)
	c:RegisterEffect(e1)
end
s.listed_series={SET_ARCHETYPE}
function s.target(e,tp,eg,ep,ev,re,r,rp,chk)
	if chk==0 then return Duel.IsPlayerCanDraw(tp,2) end
	Duel.SetTargetPlayer(tp)
	Duel.SetTargetParam(2)
	Duel.SetOperationInfo(0,CATEGORY_DRAW,nil,0,tp,2)
end
function s.activate(e,tp,eg,ep,ev,re,r,rp)
	local p,d=Duel.GetChainInfo(0,CHAININFO_TARGET_PLAYER,CHAININFO_TARGET_PARAM)
	Duel.Draw(p,d,REASON_EFFECT)
	--Also for the rest of this turn, you cannot activate monster effects, except "Archetype" monsters'
	local e1=Effect.CreateEffect(e:GetHandler())
	e1:SetDescription(aux.Stringid(id,1))
	e1:SetType(EFFECT_TYPE_FIELD)
	e1:SetProperty(EFFECT_FLAG_PLAYER_TARGET+EFFECT_FLAG_CLIENT_HINT)
	e1:SetCode(EFFECT_CANNOT_ACTIVATE)
	e1:SetTargetRange(1,0)
	e1:SetValue(function(e,re,tp) return re:IsMonsterEffect() and not re:GetHandler():IsSetCard(SET_ARCHETYPE) end)
	e1:SetReset(RESET_PHASE|PHASE_END)
	Duel.RegisterEffect(e1,tp)
end
```

---

<a id="16-fusion-monster"></a>
## 16 · Fusion Monster

> 1 "Archetype" monster + 1 LIGHT monster / If this card is Fusion Summoned: You can target 1 card on the field; destroy it.

- Fusion.AddProcMix(c,sub,insf,...): sub = Fusion Substitute monsters allowed; insf = the check passes when an effect summons it without a material group. (true,true) in 338 of 359 official uses; (false,false) for cards that forbid substitutes.
- material_setcode lets archetype-material checks see the Fusion Monster.

Source: `templates/16_fusion_monster.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	c:EnableReviveLimit()
	--Fusion Materials: 1 "Archetype" monster + 1 LIGHT monster
	Fusion.AddProcMix(c,true,true,aux.FilterBoolFunctionEx(Card.IsSetCard,SET_ARCHETYPE),aux.FilterBoolFunctionEx(Card.IsAttribute,ATTRIBUTE_LIGHT))
	--If this card is Fusion Summoned: You can target 1 card on the field; destroy it
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_DESTROY)
	e1:SetType(EFFECT_TYPE_SINGLE+EFFECT_TYPE_TRIGGER_O)
	e1:SetProperty(EFFECT_FLAG_DELAY+EFFECT_FLAG_CARD_TARGET)
	e1:SetCode(EVENT_SPSUMMON_SUCCESS)
	e1:SetCondition(function(e) return e:GetHandler():IsFusionSummoned() end)
	e1:SetTarget(s.destg)
	e1:SetOperation(s.desop)
	c:RegisterEffect(e1)
end
s.listed_series={SET_ARCHETYPE}
s.material_setcode={SET_ARCHETYPE}
function s.destg(e,tp,eg,ep,ev,re,r,rp,chk,chkc)
	if chkc then return chkc:IsOnField() end
	if chk==0 then return Duel.IsExistingTarget(nil,tp,LOCATION_ONFIELD,LOCATION_ONFIELD,1,nil) end
	Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_DESTROY)
	local g=Duel.SelectTarget(tp,nil,tp,LOCATION_ONFIELD,LOCATION_ONFIELD,1,1,nil)
	Duel.SetOperationInfo(0,CATEGORY_DESTROY,g,1,0,0)
end
function s.desop(e,tp,eg,ep,ev,re,r,rp)
	local tc=Duel.GetFirstTarget()
	if tc:IsRelateToEffect(e) then
		Duel.Destroy(tc,REASON_EFFECT)
	end
end
```

---

<a id="17-synchro-monster"></a>
## 17 · Synchro Monster

> 1 Tuner + 1+ non-Tuner monsters / If this card is Synchro Summoned: You can draw 1 card.

- Synchro.AddProcedure(c,tuner_filter,min,max,nontuner_filter,min,max).

Source: `templates/17_synchro_monster.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	c:EnableReviveLimit()
	--Synchro Summon procedure: 1 Tuner + 1+ non-Tuner monsters
	Synchro.AddProcedure(c,nil,1,1,Synchro.NonTuner(nil),1,99)
	--If this card is Synchro Summoned: You can draw 1 card
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_DRAW)
	e1:SetType(EFFECT_TYPE_SINGLE+EFFECT_TYPE_TRIGGER_O)
	e1:SetProperty(EFFECT_FLAG_DELAY+EFFECT_FLAG_PLAYER_TARGET)
	e1:SetCode(EVENT_SPSUMMON_SUCCESS)
	e1:SetCondition(function(e) return e:GetHandler():IsSynchroSummoned() end)
	e1:SetTarget(s.drtg)
	e1:SetOperation(s.drop)
	c:RegisterEffect(e1)
end
function s.drtg(e,tp,eg,ep,ev,re,r,rp,chk)
	if chk==0 then return Duel.IsPlayerCanDraw(tp,1) end
	Duel.SetTargetPlayer(tp)
	Duel.SetTargetParam(1)
	Duel.SetOperationInfo(0,CATEGORY_DRAW,nil,0,tp,1)
end
function s.drop(e,tp,eg,ep,ev,re,r,rp)
	local p,d=Duel.GetChainInfo(0,CHAININFO_TARGET_PLAYER,CHAININFO_TARGET_PARAM)
	Duel.Draw(p,d,REASON_EFFECT)
end
```

---

<a id="18-xyz-monster-detach"></a>
## 18 · Xyz Monster with a detach cost

> 2 Level 4 monsters / Once per turn (Quick Effect): You can detach 1 material from this card; this card gains 1000 ATK until the end of this turn.

- Xyz.AddProcedure(c,filter,level,count[,alternative,desc,max_count,...]).
- Stat changes usable in the Damage Step need EFFECT_FLAG_DAMAGE_STEP and aux.StatChangeDamageStepCondition.

Source: `templates/18_xyz_monster_detach.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	c:EnableReviveLimit()
	--Xyz Summon procedure: 2 Level 4 monsters
	Xyz.AddProcedure(c,nil,4,2)
	--Once per turn (Quick Effect): You can detach 1 material from this card; this card gains 1000 ATK until the end of this turn
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_ATKCHANGE)
	e1:SetType(EFFECT_TYPE_QUICK_O)
	e1:SetProperty(EFFECT_FLAG_DAMAGE_STEP)
	e1:SetCode(EVENT_FREE_CHAIN)
	e1:SetRange(LOCATION_MZONE)
	e1:SetCountLimit(1)
	e1:SetHintTiming(TIMING_DAMAGE_STEP,TIMING_DAMAGE_STEP|TIMINGS_CHECK_MONSTER)
	e1:SetCondition(aux.StatChangeDamageStepCondition)
	e1:SetCost(Cost.DetachFromSelf(1))
	e1:SetOperation(s.atkop)
	c:RegisterEffect(e1)
end
function s.atkop(e,tp,eg,ep,ev,re,r,rp)
	local c=e:GetHandler()
	if c:IsRelateToEffect(e) and c:IsFaceup() then
		c:UpdateAttack(1000,RESETS_STANDARD_DISABLE_PHASE_END)
	end
end
```

---

<a id="19-link-monster"></a>
## 19 · Link Monster

> 2+ Effect Monsters / Monsters this card points to cannot be destroyed by battle.

- Link.AddProcedure(c,filter,min[,max,group_check]); the Link Rating comes from the database.

Source: `templates/19_link_monster.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	c:EnableReviveLimit()
	--Link Summon procedure: 2+ Effect Monsters
	Link.AddProcedure(c,aux.FilterBoolFunctionEx(Card.IsType,TYPE_EFFECT),2)
	--Monsters this card points to cannot be destroyed by battle
	local e1=Effect.CreateEffect(c)
	e1:SetType(EFFECT_TYPE_FIELD)
	e1:SetCode(EFFECT_INDESTRUCTABLE_BATTLE)
	e1:SetRange(LOCATION_MZONE)
	e1:SetTargetRange(LOCATION_MZONE,LOCATION_MZONE)
	e1:SetTarget(function(e,c) return e:GetHandler():GetLinkedGroup():IsContains(c) end)
	e1:SetValue(1)
	c:RegisterEffect(e1)
end
```

---

<a id="20-fusion-spell"></a>
## 20 · Fusion Spell

> Fusion Summon 1 "Archetype" Fusion Monster from your Extra Deck, using monsters from your hand or field as material.

- Fusion.CreateSummonEff takes a named-parameter table (fusfilter, matfilter, extrafil, extraop, stage2, ...).

Source: `templates/20_fusion_spell.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--Fusion Summon 1 "Archetype" Fusion Monster from your Extra Deck, using monsters from your hand or field as material
	local e1=Fusion.CreateSummonEff({handler=c,fusfilter=aux.FilterBoolFunction(Card.IsSetCard,SET_ARCHETYPE)})
	e1:SetDescription(aux.Stringid(id,0))
	c:RegisterEffect(e1)
end
s.listed_series={SET_ARCHETYPE}
```

---

<a id="21-ritual-spell-and-monster"></a>
## 21 · Ritual Spell (the Ritual Monster itself only needs c:EnableReviveLimit())

> This card can be used to Ritual Summon any "Archetype" Ritual Monster. You must also Tribute monsters from your hand or field whose total Levels equal or exceed the Level of the Ritual Monster you Ritual Summon.

- Ritual.AddProcGreater / AddProcEqual register and return the activation; the Ritual Monster only needs c:EnableReviveLimit().

Source: `templates/21_ritual_spell_and_monster.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--Ritual Summon any "Archetype" Ritual Monster, Tributing monsters whose total Levels equal or exceed its Level
	local e1=Ritual.AddProcGreater({handler=c,filter=aux.FilterBoolFunction(Card.IsSetCard,SET_ARCHETYPE)})
	e1:SetDescription(aux.Stringid(id,0))
end
s.listed_series={SET_ARCHETYPE}
```

---

<a id="22-pendulum-monster"></a>
## 22 · Pendulum Monster with a Pendulum Effect

> [Pendulum Effect] Once per turn: You can target 1 "Archetype" monster you control; it gains 300 ATK until the end of this turn. [Monster Effect] ...

- Pendulum.AddProcedure(c) adds both the Pendulum Summon and the activation in the Pendulum Zone.
- Pendulum Effects use SetRange(LOCATION_PZONE).

Source: `templates/22_pendulum_monster.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--Pendulum Summon procedure and activation from the hand
	Pendulum.AddProcedure(c)
	--Once per turn: You can target 1 "Archetype" monster you control; it gains 300 ATK until the end of this turn
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_ATKCHANGE)
	e1:SetType(EFFECT_TYPE_IGNITION)
	e1:SetProperty(EFFECT_FLAG_CARD_TARGET)
	e1:SetRange(LOCATION_PZONE)
	e1:SetCountLimit(1)
	e1:SetTarget(s.atktg)
	e1:SetOperation(s.atkop)
	c:RegisterEffect(e1)
end
s.listed_series={SET_ARCHETYPE}
function s.atkfilter(c)
	return c:IsFaceup() and c:IsSetCard(SET_ARCHETYPE)
end
function s.atktg(e,tp,eg,ep,ev,re,r,rp,chk,chkc)
	if chkc then return chkc:IsLocation(LOCATION_MZONE) and chkc:IsControler(tp) and s.atkfilter(chkc) end
	if chk==0 then return Duel.IsExistingTarget(s.atkfilter,tp,LOCATION_MZONE,0,1,nil) end
	Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_FACEUP)
	Duel.SelectTarget(tp,s.atkfilter,tp,LOCATION_MZONE,0,1,1,nil)
end
function s.atkop(e,tp,eg,ep,ev,re,r,rp)
	local tc=Duel.GetFirstTarget()
	if tc:IsRelateToEffect(e) and tc:IsFaceup() then
		tc:UpdateAttack(300,RESETS_STANDARD_PHASE_END,e:GetHandler())
	end
end
```

---

<a id="23-flip-effect"></a>
## 23 · FLIP effect

> FLIP: Target 1 monster your opponent controls; return it to the hand.

- FLIP effects are mandatory: the target may not exist, so 'if tc and' is correct here.

Source: `templates/23_flip_effect.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--FLIP: Target 1 monster your opponent controls; return it to the hand
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_TOHAND)
	e1:SetType(EFFECT_TYPE_SINGLE+EFFECT_TYPE_FLIP)
	e1:SetProperty(EFFECT_FLAG_CARD_TARGET)
	e1:SetTarget(s.thtg)
	e1:SetOperation(s.thop)
	c:RegisterEffect(e1)
end
function s.thtg(e,tp,eg,ep,ev,re,r,rp,chk,chkc)
	if chkc then return chkc:IsLocation(LOCATION_MZONE) and chkc:IsControler(1-tp) and chkc:IsAbleToHand() end
	if chk==0 then return true end
	Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_RTOHAND)
	local g=Duel.SelectTarget(tp,Card.IsAbleToHand,tp,0,LOCATION_MZONE,1,1,nil)
	Duel.SetOperationInfo(0,CATEGORY_TOHAND,g,#g,0,0)
end
function s.thop(e,tp,eg,ep,ev,re,r,rp)
	local tc=Duel.GetFirstTarget()
	if tc and tc:IsRelateToEffect(e) then
		Duel.SendtoHand(tc,nil,REASON_EFFECT)
	end
end
```

---

<a id="24-token-summon"></a>
## 24 · Token summon

> Special Summon 1 "Template Token" (Machine/EARTH/Level 1/ATK 0/DEF 0).

- Tokens need their own database entry (conventionally passcode id+1) with type TYPES_TOKEN.
- Check Duel.IsPlayerCanSpecialSummonMonster with the Token's stats in both target and operation.

Source: `templates/24_token_summon.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--Special Summon 1 "Template Token" (Machine/EARTH/Level 1/ATK 0/DEF 0)
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_SPECIAL_SUMMON+CATEGORY_TOKEN)
	e1:SetType(EFFECT_TYPE_ACTIVATE)
	e1:SetCode(EVENT_FREE_CHAIN)
	e1:SetTarget(s.target)
	e1:SetOperation(s.activate)
	c:RegisterEffect(e1)
end
s.listed_names={id+1} --the Token has its own passcode and database entry
function s.target(e,tp,eg,ep,ev,re,r,rp,chk)
	if chk==0 then return Duel.GetLocationCount(tp,LOCATION_MZONE)>0
		and Duel.IsPlayerCanSpecialSummonMonster(tp,id+1,0,TYPES_TOKEN,0,0,1,RACE_MACHINE,ATTRIBUTE_EARTH) end
	Duel.SetOperationInfo(0,CATEGORY_TOKEN,nil,1,0,0)
	Duel.SetOperationInfo(0,CATEGORY_SPECIAL_SUMMON,nil,1,0,0)
end
function s.activate(e,tp,eg,ep,ev,re,r,rp)
	if Duel.GetLocationCount(tp,LOCATION_MZONE)<=0
		or not Duel.IsPlayerCanSpecialSummonMonster(tp,id+1,0,TYPES_TOKEN,0,0,1,RACE_MACHINE,ATTRIBUTE_EARTH) then return end
	local token=Duel.CreateToken(tp,id+1)
	Duel.SpecialSummon(token,0,tp,tp,false,false,POS_FACEUP)
end
```

---

<a id="25-destroy-replacement"></a>
## 25 · Destruction replacement from the GY

> If an "Archetype" monster you control would be destroyed by battle or card effect, you can banish this card from your GY instead.

- Replacement effects are FIELD+CONTINUOUS (not activated): target returns whether to replace, value selects the protected cards.

Source: `templates/25_destroy_replacement.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--If an "Archetype" monster you control would be destroyed by battle or card effect, you can banish this card from your GY instead
	local e1=Effect.CreateEffect(c)
	e1:SetType(EFFECT_TYPE_FIELD+EFFECT_TYPE_CONTINUOUS)
	e1:SetCode(EFFECT_DESTROY_REPLACE)
	e1:SetRange(LOCATION_GRAVE)
	e1:SetTarget(s.reptg)
	e1:SetValue(s.repval)
	e1:SetOperation(s.repop)
	c:RegisterEffect(e1)
end
s.listed_series={SET_ARCHETYPE}
function s.repfilter(c,tp)
	return c:IsFaceup() and c:IsSetCard(SET_ARCHETYPE) and c:IsLocation(LOCATION_MZONE) and c:IsControler(tp)
		and c:IsReason(REASON_BATTLE|REASON_EFFECT) and not c:IsReason(REASON_REPLACE)
end
function s.reptg(e,tp,eg,ep,ev,re,r,rp,chk)
	local c=e:GetHandler()
	if chk==0 then return c:IsAbleToRemove() and eg:IsExists(s.repfilter,1,nil,tp) end
	return Duel.SelectEffectYesNo(tp,c,96)
end
function s.repval(e,c)
	return s.repfilter(c,e:GetHandlerPlayer())
end
function s.repop(e,tp,eg,ep,ev,re,r,rp)
	Duel.Remove(e:GetHandler(),POS_FACEUP,REASON_EFFECT|REASON_REPLACE)
end
```

---

<a id="26-battle-destroying-trigger"></a>
## 26 · Trigger when this card destroys a monster by battle

> If this card destroys an opponent's monster by battle: You can inflict damage to your opponent equal to that monster's original ATK.

- aux.bdocon: this card is still related to the battle and fought an opponent's monster.

Source: `templates/26_battle_destroying_trigger.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--If this card destroys an opponent's monster by battle: You can inflict damage to your opponent equal to that monster's original ATK
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_DAMAGE)
	e1:SetType(EFFECT_TYPE_SINGLE+EFFECT_TYPE_TRIGGER_O)
	e1:SetProperty(EFFECT_FLAG_PLAYER_TARGET)
	e1:SetCode(EVENT_BATTLE_DESTROYING)
	e1:SetCondition(aux.bdocon)
	e1:SetTarget(s.damtg)
	e1:SetOperation(s.damop)
	c:RegisterEffect(e1)
end
function s.damtg(e,tp,eg,ep,ev,re,r,rp,chk)
	local bc=e:GetHandler():GetBattleTarget()
	if chk==0 then return bc:GetBaseAttack()>0 end
	local dam=bc:GetBaseAttack()
	Duel.SetTargetPlayer(1-tp)
	Duel.SetTargetParam(dam)
	Duel.SetOperationInfo(0,CATEGORY_DAMAGE,nil,0,1-tp,dam)
end
function s.damop(e,tp,eg,ep,ev,re,r,rp)
	local p,d=Duel.GetChainInfo(0,CHAININFO_TARGET_PLAYER,CHAININFO_TARGET_PARAM)
	Duel.Damage(p,d,REASON_EFFECT)
end
```

---

<a id="27-leaves-field-by-opponent"></a>
## 27 · Trigger when this card leaves the field because of the opponent

> If this card in your possession is destroyed by an opponent's card and sent to your GY: You can Special Summon 1 "Archetype" monster from your Deck.

- rp==1-tp with REASON_DESTROY checks 'destroyed by an opponent's card'.

Source: `templates/27_leaves_field_by_opponent.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--If this card in your possession is destroyed by an opponent's card and sent to your GY: You can Special Summon 1 "Archetype" monster from your Deck
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_SPECIAL_SUMMON)
	e1:SetType(EFFECT_TYPE_SINGLE+EFFECT_TYPE_TRIGGER_O)
	e1:SetProperty(EFFECT_FLAG_DELAY)
	e1:SetCode(EVENT_TO_GRAVE)
	e1:SetCondition(s.spcon)
	e1:SetTarget(s.sptg)
	e1:SetOperation(s.spop)
	c:RegisterEffect(e1)
end
s.listed_series={SET_ARCHETYPE}
function s.spcon(e,tp,eg,ep,ev,re,r,rp)
	local c=e:GetHandler()
	return c:IsReason(REASON_DESTROY) and c:IsPreviousControler(tp) and rp==1-tp
end
function s.spfilter(c,e,tp)
	return c:IsSetCard(SET_ARCHETYPE) and c:IsCanBeSpecialSummoned(e,0,tp,false,false)
end
function s.sptg(e,tp,eg,ep,ev,re,r,rp,chk)
	if chk==0 then return Duel.GetLocationCount(tp,LOCATION_MZONE)>0
		and Duel.IsExistingMatchingCard(s.spfilter,tp,LOCATION_DECK,0,1,nil,e,tp) end
	Duel.SetOperationInfo(0,CATEGORY_SPECIAL_SUMMON,nil,1,tp,LOCATION_DECK)
end
function s.spop(e,tp,eg,ep,ev,re,r,rp)
	if Duel.GetLocationCount(tp,LOCATION_MZONE)<=0 then return end
	Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_SPSUMMON)
	local g=Duel.SelectMatchingCard(tp,s.spfilter,tp,LOCATION_DECK,0,1,1,nil,e,tp)
	if #g>0 then
		Duel.SpecialSummon(g,0,tp,tp,false,false,POS_FACEUP)
	end
end
```

---

<a id="28-temporary-banish"></a>
## 28 · Banish until a later phase

> (Quick Effect): You can target 1 face-up monster your opponent controls; banish it until the End Phase.

- aux.RemoveUntil banishes temporarily and registers the return (aux.DefaultFieldReturnOp handles zones).

Source: `templates/28_temporary_banish.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--(Quick Effect): You can target 1 face-up monster your opponent controls; banish it until the End Phase
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_REMOVE)
	e1:SetType(EFFECT_TYPE_QUICK_O)
	e1:SetProperty(EFFECT_FLAG_CARD_TARGET)
	e1:SetCode(EVENT_FREE_CHAIN)
	e1:SetRange(LOCATION_MZONE)
	e1:SetCountLimit(1,id)
	e1:SetHintTiming(0,TIMINGS_CHECK_MONSTER_E)
	e1:SetTarget(s.rmtg)
	e1:SetOperation(s.rmop)
	c:RegisterEffect(e1)
end
function s.rmfilter(c)
	return c:IsFaceup() and c:IsAbleToRemove()
end
function s.rmtg(e,tp,eg,ep,ev,re,r,rp,chk,chkc)
	if chkc then return chkc:IsLocation(LOCATION_MZONE) and chkc:IsControler(1-tp) and s.rmfilter(chkc) end
	if chk==0 then return Duel.IsExistingTarget(s.rmfilter,tp,0,LOCATION_MZONE,1,nil) end
	Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_REMOVE)
	local g=Duel.SelectTarget(tp,s.rmfilter,tp,0,LOCATION_MZONE,1,1,nil)
	Duel.SetOperationInfo(0,CATEGORY_REMOVE,g,1,0,0)
end
function s.rmop(e,tp,eg,ep,ev,re,r,rp)
	local tc=Duel.GetFirstTarget()
	if tc:IsRelateToEffect(e) then
		aux.RemoveUntil(tc,nil,REASON_EFFECT,PHASE_END,id,e,tp,aux.DefaultFieldReturnOp)
	end
end
```

---

<a id="29-mandatory-end-phase"></a>
## 29 · Mandatory trigger during the End Phase

> Once per turn, during the End Phase: Send this card to the GY.

- Mandatory (TRIGGER_F) phase trigger with a soft once-per-turn limit.

Source: `templates/29_mandatory_end_phase.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--Once per turn, during the End Phase: Send this card to the GY
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_TOGRAVE)
	e1:SetType(EFFECT_TYPE_FIELD+EFFECT_TYPE_TRIGGER_F)
	e1:SetCode(EVENT_PHASE+PHASE_END)
	e1:SetRange(LOCATION_MZONE)
	e1:SetCountLimit(1)
	e1:SetTarget(s.tgtg)
	e1:SetOperation(s.tgop)
	c:RegisterEffect(e1)
end
function s.tgtg(e,tp,eg,ep,ev,re,r,rp,chk)
	if chk==0 then return true end
	Duel.SetOperationInfo(0,CATEGORY_TOGRAVE,e:GetHandler(),1,0,0)
end
function s.tgop(e,tp,eg,ep,ev,re,r,rp)
	local c=e:GetHandler()
	if c:IsRelateToEffect(e) then
		Duel.SendtoGrave(c,REASON_EFFECT)
	end
end
```

---

<a id="30-counters"></a>
## 30 · Counters (permit, place on activation of Spells, remove as cost)

> Each time a Spell Card is activated, place 1 Spell Counter on this card when that Spell resolves. You can remove 2 Spell Counters from this card; draw 1 card.

- aux.chainreg flags the card when a chain link is added; EVENT_CHAIN_SOLVED adds the counter when that Spell resolves.

Source: `templates/30_counters.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	c:EnableCounterPermit(COUNTER_SPELL)
	--Each time a Spell Card is activated, place 1 Spell Counter on this card when that Spell resolves
	local e0=Effect.CreateEffect(c)
	e0:SetType(EFFECT_TYPE_FIELD+EFFECT_TYPE_CONTINUOUS)
	e0:SetCode(EVENT_CHAINING)
	e0:SetRange(LOCATION_MZONE)
	e0:SetOperation(aux.chainreg)
	c:RegisterEffect(e0)
	local e1=Effect.CreateEffect(c)
	e1:SetType(EFFECT_TYPE_FIELD+EFFECT_TYPE_CONTINUOUS)
	e1:SetProperty(EFFECT_FLAG_CANNOT_DISABLE)
	e1:SetCode(EVENT_CHAIN_SOLVED)
	e1:SetRange(LOCATION_MZONE)
	e1:SetOperation(function(e,tp,eg,ep,ev,re,r,rp)
		local c=e:GetHandler()
		if re:IsHasType(EFFECT_TYPE_ACTIVATE) and re:IsSpellEffect() and c:GetFlagEffect(1)>0 then
			c:AddCounter(COUNTER_SPELL,1)
		end
	end)
	c:RegisterEffect(e1)
	--You can remove 2 Spell Counters from this card; draw 1 card
	local e2=Effect.CreateEffect(c)
	e2:SetDescription(aux.Stringid(id,0))
	e2:SetCategory(CATEGORY_DRAW)
	e2:SetType(EFFECT_TYPE_IGNITION)
	e2:SetProperty(EFFECT_FLAG_PLAYER_TARGET)
	e2:SetRange(LOCATION_MZONE)
	e2:SetCost(Cost.RemoveCounterFromSelf(COUNTER_SPELL,2))
	e2:SetTarget(s.drtg)
	e2:SetOperation(s.drop)
	c:RegisterEffect(e2)
end
s.counter_place_list={COUNTER_SPELL}
function s.drtg(e,tp,eg,ep,ev,re,r,rp,chk)
	if chk==0 then return Duel.IsPlayerCanDraw(tp,1) end
	Duel.SetTargetPlayer(tp)
	Duel.SetTargetParam(1)
	Duel.SetOperationInfo(0,CATEGORY_DRAW,nil,0,tp,1)
end
function s.drop(e,tp,eg,ep,ev,re,r,rp)
	local p,d=Duel.GetChainInfo(0,CHAININFO_TARGET_PLAYER,CHAININFO_TARGET_PARAM)
	Duel.Draw(p,d,REASON_EFFECT)
end
```

---

<a id="31-summon-condition-nomi"></a>
## 31 · Cannot be Normal Summoned/Set, special summon condition

> Cannot be Normal Summoned/Set. Must be Special Summoned (from your hand) by banishing 2 "Archetype" monsters from your GY.

- EFFECT_SPSUMMON_CONDITION with aux.FALSE forbids other Special Summons; the procedure is the only way.
- The procedure's target selects and stores the cost group; the operation pays it.

Source: `templates/31_summon_condition_nomi.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	c:EnableReviveLimit()
	--Must be Special Summoned (from your hand) by banishing 2 "Archetype" monsters from your GY
	local e0=Effect.CreateEffect(c)
	e0:SetType(EFFECT_TYPE_SINGLE)
	e0:SetProperty(EFFECT_FLAG_CANNOT_DISABLE+EFFECT_FLAG_UNCOPYABLE)
	e0:SetCode(EFFECT_SPSUMMON_CONDITION)
	e0:SetValue(aux.FALSE)
	c:RegisterEffect(e0)
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetType(EFFECT_TYPE_FIELD)
	e1:SetProperty(EFFECT_FLAG_UNCOPYABLE)
	e1:SetCode(EFFECT_SPSUMMON_PROC)
	e1:SetRange(LOCATION_HAND)
	e1:SetCondition(s.spcon)
	e1:SetTarget(s.sptg)
	e1:SetOperation(s.spop)
	c:RegisterEffect(e1)
end
s.listed_series={SET_ARCHETYPE}
function s.spcostfilter(c)
	return c:IsSetCard(SET_ARCHETYPE) and c:IsMonster() and c:IsAbleToRemoveAsCost()
end
function s.spcon(e,c)
	if c==nil then return true end
	local tp=c:GetControler()
	return Duel.GetLocationCount(tp,LOCATION_MZONE)>0
		and Duel.IsExistingMatchingCard(s.spcostfilter,tp,LOCATION_GRAVE,0,2,nil)
end
function s.sptg(e,tp,eg,ep,ev,re,r,rp,chk,c)
	local g=Duel.GetMatchingGroup(s.spcostfilter,tp,LOCATION_GRAVE,0,nil)
	local sg=aux.SelectUnselectGroup(g,e,tp,2,2,nil,1,tp,HINTMSG_REMOVE,nil,nil,true)
	if #sg>0 then
		sg:KeepAlive()
		e:SetLabelObject(sg)
		return true
	end
	return false
end
function s.spop(e,tp,eg,ep,ev,re,r,rp,c)
	local sg=e:GetLabelObject()
	if not sg then return end
	Duel.Remove(sg,POS_FACEUP,REASON_COST)
	sg:DeleteGroup()
end
```

---

<a id="32-conjunctions"></a>
## 32 · Resolution conjunctions ("and if you do", "then", "also")

> Target 1 monster in your GY; Special Summon it, and if you do, you take 500 damage, then you can draw 1 card, also you cannot Normal Summon/Set for the rest of this turn.

- 'and if you do' = nested condition without BreakEffect; 'then' = BreakEffect; 'also' = unconditional.

Source: `templates/32_conjunctions.lua`

```lua
--(Japanese name)
--Template
local s,id=GetID()
function s.initial_effect(c)
	--Target 1 monster in your GY; Special Summon it, and if you do, you take 500 damage, then you can draw 1 card, also you cannot Normal Summon/Set for the rest of this turn
	local e1=Effect.CreateEffect(c)
	e1:SetDescription(aux.Stringid(id,0))
	e1:SetCategory(CATEGORY_SPECIAL_SUMMON+CATEGORY_DAMAGE)
	e1:SetType(EFFECT_TYPE_ACTIVATE)
	e1:SetProperty(EFFECT_FLAG_CARD_TARGET)
	e1:SetCode(EVENT_FREE_CHAIN)
	e1:SetTarget(s.target)
	e1:SetOperation(s.activate)
	c:RegisterEffect(e1)
end
function s.spfilter(c,e,tp)
	return c:IsCanBeSpecialSummoned(e,0,tp,false,false)
end
function s.target(e,tp,eg,ep,ev,re,r,rp,chk,chkc)
	if chkc then return chkc:IsLocation(LOCATION_GRAVE) and chkc:IsControler(tp) and s.spfilter(chkc,e,tp) end
	if chk==0 then return Duel.GetLocationCount(tp,LOCATION_MZONE)>0
		and Duel.IsExistingTarget(s.spfilter,tp,LOCATION_GRAVE,0,1,nil,e,tp) end
	Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_SPSUMMON)
	local g=Duel.SelectTarget(tp,s.spfilter,tp,LOCATION_GRAVE,0,1,1,nil,e,tp)
	Duel.SetOperationInfo(0,CATEGORY_SPECIAL_SUMMON,g,1,0,0)
	Duel.SetOperationInfo(0,CATEGORY_DAMAGE,nil,0,tp,500)
	Duel.SetPossibleOperationInfo(0,CATEGORY_DRAW,nil,0,tp,1)
end
function s.activate(e,tp,eg,ep,ev,re,r,rp)
	local tc=Duel.GetFirstTarget()
	--"and if you do": the second part depends on the first one succeeding; no BreakEffect (simultaneous)
	if tc:IsRelateToEffect(e) and Duel.SpecialSummon(tc,0,tp,tp,false,false,POS_FACEUP)>0
		and Duel.Damage(tp,500,REASON_EFFECT)>0
		--"then you can": sequential and optional; ask, then separate the timing with BreakEffect
		and Duel.IsPlayerCanDraw(tp,1) and Duel.SelectYesNo(tp,aux.Stringid(id,1)) then
		Duel.BreakEffect()
		Duel.Draw(tp,1,REASON_EFFECT)
	end
	--"also": applies even if the previous parts did not happen
	local e1=Effect.CreateEffect(e:GetHandler())
	e1:SetDescription(aux.Stringid(id,2))
	e1:SetType(EFFECT_TYPE_FIELD)
	e1:SetProperty(EFFECT_FLAG_PLAYER_TARGET+EFFECT_FLAG_CLIENT_HINT)
	e1:SetCode(EFFECT_CANNOT_SUMMON)
	e1:SetTargetRange(1,0)
	e1:SetReset(RESET_PHASE|PHASE_END)
	Duel.RegisterEffect(e1,tp)
	local e2=e1:Clone()
	e2:SetCode(EFFECT_CANNOT_MSET)
	Duel.RegisterEffect(e2,tp)
end
```
