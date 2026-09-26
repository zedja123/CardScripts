# 05 · API quick reference

The ~150 functions and constants that cover almost every script, ordered by topic.
Signatures were cross-checked against the C++ bindings in ygopro-core (`lib*.cpp`) and the
Lua definitions in CardScripts; the "uses" column is the number of official/pre-release
scripts that call the function (a proxy for how idiomatic it is).

Notation: `[x]` optional, `a|b` alternative types, `ex` = card/group excluded (pass `nil`
when none; it is **required** where marked `ex!`), `...` = extra arguments forwarded to the
filter function.

## How to look anything else up

| Need | Where |
|---|---|
| Does a name exist at runtime? | `grep -P '^Duel\.Name\t' ~/.cache/edopro-card-scripting/symbols.tsv` (created by `loadcheck.py symbols`) |
| C++ function body (exact parameters) | `grep -n 'LUA_FUNCTION(Name)' ygopro-core/lib*.cpp` (`libcard` → `Card.`, `libduel` → `Duel.`, `libeffect` → `Effect.`, `libgroup` → `Group.`, `libdebug` → `Debug.`) |
| Lua helper (aux, Cost, procedures, Card/Duel extensions) | `grep -n 'function Name\|Name *=' CardScripts/*.lua` |
| Documentation | `scrapiyard/api/functions/<Namespace>/<Name>.yml` (907 of 3,048 entries are still marked `under-construction`), the CardScripts wiki (`Scripting-Library:-*` pages, last updated 2024-06), or `scrapiyard/api/constants/<Enum>/<NAME>.yml` for constants |
| How real cards use it | `grep -rn 'Name(' CardScripts/official \| head` or `cdb.py search ... --code 'Name\('` |

---

## 1. Effects (`Effect.` / methods on `e`)

| Signature | Meaning | Uses |
|---|---|---|
| `Effect.CreateEffect(c)` | New effect owned by card `c` | 13,478 |
| `e:SetDescription(aux.Stringid(id,n))` | Client description / effect name | 10,283 |
| `e:SetCategory(CATEGORY_A+CATEGORY_B)` | What the effect can do | 11,496 |
| `e:SetType(EFFECT_TYPE_...)` | Kind of effect (02 §3) | 13,478 |
| `e:SetProperty(EFFECT_FLAG_...[,EFFECT_FLAG2_...])` | Flags | 10,424 |
| `e:SetCode(EVENT_... \| EFFECT_...)` | Event for triggers, effect code for continuous effects | 12,868 |
| `e:SetRange(LOCATION_...)` | Where the handler must be | 9,272 |
| `e:SetTargetRange(self_loc,opp_loc)` / `(1,0)` with `PLAYER_TARGET` | Affected locations / players of FIELD effects | 3,089 |
| `e:SetCountLimit(count[,code\|{code,index}[,flags]])` | Usage limits (02 §5) | 8,042 |
| `e:SetCondition(f)` / `SetCost(f)` / `SetTarget(f)` / `SetOperation(f)` | The four functions; `nil` is an error except for `SetOperation` | |
| `e:SetValue(v)` | Number, boolean or function, meaning depends on the code | 6,126 |
| `e:SetReset(flags[,count])` | When a non-permanent effect ends (07 §9) | 5,210 |
| `e:SetHintTiming(self_timing[,opp_timing])` | Client prompt timings for Quick Effects | 2,112 |
| `e:SetLabel(n,...)` / `e:GetLabel()` / `e:SetLabelObject(o)` / `e:GetLabelObject()` | Store data on the effect | 1,640 |
| `e:Clone()` | Copy (then change code/range) | 2,440 |
| `e:GetHandler()` / `e:GetOwner()` / `e:GetHandlerPlayer()` / `e:GetOwnerPlayer()` | Card/player the effect belongs to | 10,382 |
| `e:IsHasType(t)` / `e:IsHasProperty(p)` / `e:IsActivated()` | Inspect effects (e.g. `re`) | |
| `e:IsMonsterEffect()` / `IsSpellEffect()` / `IsTrapEffect()` / `IsSpellTrapEffect()` | Kind of an activated effect `re` | 701 |
| `e:GetChainData()` | Per-chain-link data table (`chain.lua`) | 57 |
| `e:Reset()` | Remove the effect | |
| `c:RegisterEffect(e[,forced])` | Register on a card | 13,526 |
| `Duel.RegisterEffect(e,player)` | Register on a player (lingering/global effects) | 2,025 |
| `aux.Stringid(id,n)` | Description code for database string `str(n+1)` | 10,506 |

## 2. Selecting and counting cards (`Duel.`)

| Signature | Meaning | Uses |
|---|---|---|
| `Duel.IsExistingMatchingCard(f,tp,s_loc,o_loc,count,ex!,...)` | At least `count` cards match (no targeting) | 7,345 |
| `Duel.GetMatchingGroup(f,tp,s_loc,o_loc,ex!,...)` | Group of matching cards | 3,222 |
| `Duel.GetMatchingGroupCount(f,tp,s_loc,o_loc,ex!,...)` | Count of matching cards | 587 |
| `Duel.SelectMatchingCard(sel_p,f,tp,s_loc,o_loc,min,max,[cancel,]ex!,...)` | Player selects (no targeting) | 5,488 |
| `Duel.IsExistingTarget(f,tp,s_loc,o_loc,count,ex!,...)` | At least `count` **targetable** cards match | 4,613 |
| `Duel.SelectTarget(sel_p,f,tp,s_loc,o_loc,min,max,[cancel,]ex!,...)` | Select and target (needs `EFFECT_FLAG_CARD_TARGET`) | 4,812 |
| `Duel.GetFirstTarget()` / `Duel.GetTargetCards(e)` | Targets still related to the chain link | 4,513 / 661 |
| `Duel.SetTargetCard(g)` | Mark cards as related without selecting (event cards, etc.) | 715 |
| `Duel.GetFieldGroup(tp,s_loc,o_loc)` / `Duel.GetFieldGroupCount(...)` | All cards in locations | 469 / 1,016 |
| `Duel.GetDecktopGroup(tp,n)` | Top cards of the Deck | |
| `Duel.GetOperatedGroup()` | Cards affected by the last operation | |
| `aux.SelectUnselectGroup(g,e,tp,min,max,rescon,chk,[sel_p,hint,cancelcon,breakcon,cancelable])` | Check (`chk=0`) or select (`chk=1`) a subgroup satisfying `rescon(sg,e,tp,mg)` | 811 |
| `aux.dncheck` / `aux.dpcheck(Card.GetX)` | `rescon` helpers: different names / different property | |
| `Duel.Hint(HINT_SELECTMSG,tp,HINTMSG_...)` | Selection prompt text (before every selection) | 9,478 |
| `Duel.HintSelection(g)` | Show the selected cards to both players | 830 |
| `Duel.ConfirmCards(1-tp,g)` | Reveal cards to a player | 2,617 |

Filter helpers: `aux.FaceupFilter(f,...)`, `aux.FilterBoolFunction(f,...)`,
`aux.FilterBoolFunctionEx(f,value)` (material filters), `aux.TargetBoolFunction(f,...)`
(for `SetTarget` of FIELD continuous effects), `aux.NecroValleyFilter(f)` (non-targeted
selection from the GY), `aux.AND(f1,f2)`, `aux.OR(...)`, `aux.NOT(f)`.

## 3. Moving cards (`Duel.`)

All return the number of cards moved; check it (`>0`) before "and if you do" parts.

| Signature | Meaning | Uses |
|---|---|---|
| `Duel.SpecialSummon(g,sumtype,sum_p,target_p,nocheck,nolimit,pos[,zone])` | Special Summon (`sumtype` 0 for effects) | 4,477 |
| `Duel.SpecialSummonStep(c,...)` + `Duel.SpecialSummonComplete()` | Summon several cards one by one, then complete | 790 |
| `Duel.SendtoHand(g,player\|nil,reason)` | To hand (`nil` = owner's hand) | 2,976 |
| `Duel.SendtoGrave(g,reason)` | To GY | 1,869 |
| `Duel.Remove(g,pos\|nil,reason)` | Banish (`POS_FACEUP` / `POS_FACEDOWN`) | 1,538 |
| `Duel.Destroy(g,reason[,dest])` | Destroy | 2,768 |
| `Duel.SendtoDeck(g,player\|nil,seq,reason)` | To Deck; `SEQ_DECKSHUFFLE`, `SEQ_DECKTOP`, `SEQ_DECKBOTTOM` | 935 |
| `Duel.Release(g,reason)` | Tribute | 745 |
| `Duel.DiscardHand(tp,f,min,max,reason,ex!,...)` | Discard (`REASON_EFFECT\|REASON_DISCARD`) | 624 |
| `Duel.DiscardDeck(tp,n,reason)` | Send the top `n` cards to the GY (mill) | |
| `Duel.Draw(tp,n,reason)` | Draw | 858 |
| `Duel.SSet(tp,g[,target_p,confirm])` | Set Spells/Traps | |
| `Duel.MoveToField(c,move_p,target_p,dest,pos,enabled[,zone])` | Place a card on the field (not a summon) | |
| `Duel.Equip(tp,equip_card,target[,faceup,is_step])` | Equip | |
| `Duel.Overlay(xyz_card,g)` | Attach as material (check `Card.IsCanBeXyzMaterial` first) | |
| `Duel.ChangePosition(g,pos)` | Change battle position | 507 |
| `Duel.GetControl(g,tp[,reset_phase,reset_count])` | Take control | |
| `Duel.Summon(tp,c,ignore_count,effect\|nil[,min_tribute,zone])` | Normal Summon by effect | |
| `aux.RemoveUntil(g,pos\|nil,reason,phase,id,e,tp,return_op)` | Banish until a phase, then return | 36 |
| `aux.ToHandOrElse(g,tp[,check,oper,str])` | "add to hand or <else>" choice | 130 |
| `Duel.ShuffleHand(tp)` / `Duel.ShuffleDeck(tp)` | Shuffle | |
| `Duel.CreateToken(tp,code)` | Create a Token (then `Duel.SpecialSummon`) | |

Reasons: `REASON_EFFECT` for resolutions, `REASON_COST` for costs (plus `REASON_DISCARD`
when discarding, `REASON_RELEASE` implied by `Duel.Release`), `REASON_RULE` for game rules.

## 4. Life points, battle, chain

| Signature | Meaning |
|---|---|
| `Duel.Damage(p,amount,reason)` / `Duel.Recover(p,amount,reason)` | Damage / gain LP |
| `Duel.GetLP(p)` / `Duel.CheckLPCost(p,n)` / `Duel.PayLPCost(p,n)` | LP |
| `Duel.GetAttacker()` / `Duel.GetAttackTarget()` / `c:GetBattleTarget()` / `c:IsRelateToBattle()` | Battle participants |
| `Duel.NegateAttack()` | Negate the attack |
| `Duel.NegateActivation(ev)` / `Duel.IsChainNegatable(ev)` | Negate an activation (chain link `ev`) |
| `Duel.NegateEffect(ev)` / `Duel.IsChainDisablable(ev)` | Negate an effect |
| `Duel.GetChainInfo(ch,CHAININFO_...)` | Chain link data (`0` = current) |
| `Duel.GetCurrentChain()` | Current chain length |
| `Duel.SetOperationInfo(0,cat,g\|nil,count,player,param)` / `Duel.SetPossibleOperationInfo(...)` | Declare what the activation does |
| `Duel.SetTargetPlayer(p)` / `Duel.SetTargetParam(n)` | Store player/number for the resolution (draw, damage) |
| `Duel.BreakEffect()` | Separate "then" steps |
| `Duel.SetChainLimit(f)` | Restrict chaining to this link |

## 5. Phase, turn and field state

| Signature | Meaning |
|---|---|
| `Duel.IsTurnPlayer(p)` | Is it `p`'s turn |
| `Duel.IsMainPhase([p])` / `Duel.IsBattlePhase([p])` / `Duel.IsDamageStep()` / `Duel.IsPhase(PHASE_...)` | Phase checks (Lua helpers) |
| `Duel.GetCurrentPhase()` / `Duel.GetTurnCount()` | Raw phase / turn number |
| `Duel.GetLocationCount(p,LOCATION_MZONE\|SZONE)` | Free zones |
| `Duel.GetMZoneCount(p,leaving_cards)` | Free Monster Zones after `leaving_cards` leave |
| `Duel.GetLocationCountFromEx(p[,rp,leaving,sc])` | Zones usable by an Extra Deck monster |
| `Duel.IsPlayerCanDraw(p[,n])` / `Duel.IsPlayerCanSpecialSummonMonster(p,code[,...stats])` | Player permissions |
| `Duel.IsPlayerAffectedByEffect(p,code)` | Player-affecting effect present |
| `Duel.RegisterFlagEffect(p,code,reset,prop,count)` / `Duel.HasFlagEffect(p,code)` / `Duel.GetFlagEffect(p,code)` | Player flags |
| `Duel.AddCustomActivityCounter(id,ACTIVITY_...,f)` / `Duel.GetCustomActivityCount(id,p,ACTIVITY_...)` | Activity tracking for locks |
| `Duel.SelectYesNo(p,desc)` / `Duel.SelectOption(p,desc1,...)` / `Duel.SelectEffect(p,{cond,desc},...)` / `Duel.SelectEffectYesNo(p,c[,desc])` | Player choices |
| `Duel.AnnounceCard(p,...)` / `AnnounceNumber` / `AnnounceAttribute` / `AnnounceRace` / `AnnounceLevel` | Declarations |
| `Duel.TossCoin(p,n)` / `Duel.CallCoin(p)` / `Duel.TossDice(p,n)` | Randomness |

## 6. Card properties (`Card.` / methods on `c`)

| Group | Methods |
|---|---|
| Identity | `IsCode(...)`, `GetCode()`, `IsOriginalCode(...)`, `IsSetCard(SET_X)`, `IsOriginalSetCard`, `ListsCode(...)`, `ListsArchetype(...)` |
| Type | `IsMonster()`, `IsSpell()`, `IsTrap()`, `IsSpellTrap()`, `IsType(TYPE_...)`, `IsOriginalType`, `IsEffectMonster()`, `IsNonEffectMonster()`, `IsFieldSpell()`, `IsContinuousSpell()`, `IsNormalTrap()`, `IsXyzMonster()`, `IsLinkMonster()`, `IsRitualMonster()` |
| Stats | `IsRace(RACE_...)`, `IsAttribute(ATTRIBUTE_...)`, `IsRaceExcept`, `IsAttributeExcept`, `GetLevel()`, `IsLevel(...)`, `IsLevelBelow(n)`, `IsLevelAbove(n)`, `HasLevel()`, `GetRank()`, `GetLink()`, `GetAttack()`, `GetDefense()`, `GetBaseAttack()`, `IsAttackBelow(n)`, `IsAttackAbove(n)`, `HasNonZeroAttack()` |
| Position/location | `IsLocation(LOCATION_...)`, `IsOnField()`, `IsFaceup()`, `IsFacedown()`, `IsPosition(POS_...)`, `IsAttackPos()`, `IsDefensePos()`, `GetSequence()`, `IsControler(p)`, `GetControler()`, `GetOwner()`, `IsPublic()` |
| History | `IsPreviousLocation(...)`, `IsPreviousControler(p)`, `IsPreviousPosition(...)`, `IsReason(REASON_...)`, `GetReasonPlayer()`, `IsReasonPlayer(p)`, `GetReasonCard()`, `GetReasonEffect()`, `IsSummonLocation(...)`, `IsSummonType(...)`, `IsFusionSummoned()`/`IsSynchroSummoned()`/..., `IsSpecialSummoned()`, `IsStatus(STATUS_...)`, `GetTurnID()` |
| Abilities (can it be ...) | `IsAbleToHand()`, `IsAbleToGrave()`, `IsAbleToRemove()`, `IsAbleToDeck()`, `IsAbleToExtra()`, `IsAbleToHandAsCost()`, `IsAbleToGraveAsCost()`, `IsAbleToRemoveAsCost()`, `IsDiscardable()`, `IsReleasable()`, `IsDestructable()`, `IsCanBeSpecialSummoned(e,0,tp,false,false[,pos])`, `IsSummonable(ignore_count,effect\|nil)`, `IsSSetable()`, `IsCanBeEffectTarget(e)`, `IsCanBeXyzMaterial(xyz,tp,reason)`, `IsCanChangePosition()`, `IsCanTurnSet()`, `IsCanAddCounter(...)`, `IsForbidden()` |
| Relations | `IsRelateToEffect(e)`, `IsRelateToBattle()`, `CreateEffectRelation(e)`, `IsImmuneToEffect(e)`, `IsDisabled()`, `IsNegatable()`, `IsNegatableMonster()` |
| Groups from a card | `GetOverlayGroup()`, `GetOverlayCount()`, `GetEquipTarget()`, `GetEquipGroup()`, `GetLinkedGroup()`, `GetMaterial()`, `GetColumnGroup()` |
| Helpers that register effects | `UpdateAttack(n[,reset,rc])`, `UpdateDefense`, `UpdateLevel`, `NegateEffects(rc[,reset])`, `AddPiercing()`, `RegisterFlagEffect(code,reset,prop,count)`, `HasFlagEffect(code)`, `AddCounter(COUNTER_X,n)`, `RemoveCounter(tp,COUNTER_X,n,reason)`, `GetCounter(COUNTER_X)`, `RemoveOverlayCard(tp,min,max,reason)`, `CheckRemoveOverlayCard(tp,n,reason)` |
| Card setup (initial_effect) | `EnableReviveLimit()`, `EnableUnsummonable()`, `AddMustBeSpecialSummoned()`, `EnableCounterPermit(COUNTER_X[,loc])`, `SetUniqueOnField(1,0,id)`, `SetSPSummonOnce(id)` |

## 7. Groups (`Group.` / methods on `g`)

`#g`, `g:GetFirst()`, `for tc in g:Iter() do`, `g:Filter(f,ex!,...)`, `g:Match(f,ex,...)`
(in place), `g:FilterCount(f,ex,...)`, `g:IsExists(f,count,ex,...)`, `g:IsContains(c)`,
`g:Select(p,min,max,ex!)`, `g:FilterSelect(p,f,min,max,ex,...)`, `g:RandomSelect(p,n)`,
`g:GetClassCount(f)`, `g:GetSum(f)`, `g:Merge(g2)`, `g:AddCard(c)`, `g:RemoveCard(c)`,
`g:Sub(g2)`, `g:Split(f,ex,...)`, `g:KeepAlive()` / `g:DeleteGroup()`,
`Group.CreateGroup()`, `Group.FromCards(c1,...)`.

## 8. Costs (`Cost.`)

`Cost.SelfBanish`, `Cost.SelfTribute`, `Cost.SelfToGrave`, `Cost.SelfDiscard`,
`Cost.SelfDiscardToGrave`, `Cost.SelfReveal`, `Cost.SelfToHand`, `Cost.SelfToDeck`,
`Cost.SelfToExtra`, `Cost.SelfChangePosition(pos)`, `Cost.DetachFromSelf(min[,max,op])`,
`Cost.DetachChoiceFromSelf({counts},op)`, `Cost.PayLP(n[,pay_until])`,
`Cost.Discard([filter,other,min,max,op])`, `Cost.Reveal([filter,other,min,max,op,loc])`,
`Cost.RemoveCounterFromSelf(COUNTER_X,n)`, `Cost.RemoveCounterFromField(COUNTER_X,n)`,
`Cost.AND(c1,c2,...)`, `Cost.Choice({cost,desc[,check]},...)`, `Cost.Replaceable(base)`,
`Cost.SoftOncePerChain(id)`, `Cost.HardOncePerChain(id)`, `Cost.SoftOncePerBattle(id)`,
`Cost.HardOncePerBattle(id)`, `Cost.HintSelectedEffect`.
After a cost, `e:GetChainData()` holds `cost_discarded_cards`, `cost_detached_materials`,
`cost_lp_paid` where applicable.

## 9. Procedures

| Call | For |
|---|---|
| `Fusion.AddProcMix(c,true,true,mat1,mat2,...)` (codes or filters) / `AddProcMixN(c,true,true,mat,n)` / `AddProcMixRep(...)` / `AddContactProc(...)` | Fusion Materials |
| `Fusion.CreateSummonEff{handler=c,fusfilter=...,matfilter=...,extrafil=...,extraop=...,stage2=...}` | Fusion Spells / "Fusion Summon" effects |
| `Synchro.AddProcedure(c,tuner_f,1,1,Synchro.NonTuner(f),1,99)` | Synchro Materials (`nil` = any) |
| `Xyz.AddProcedure(c,f,level,count[,alterf,desc,maxcount,op])` (`Xyz.InfiniteMats` for "2+") | Xyz Materials |
| `Link.AddProcedure(c,f,min[,max,group_check])` | Link Materials |
| `Pendulum.AddProcedure(c[,reg])` | Pendulum Summon + Pendulum Zone activation |
| `Ritual.AddProcGreater{handler=c,filter=...}` / `Ritual.AddProcEqual{...}` / `Ritual.Target{...}` + `Ritual.Operation{...}` | Ritual Spells and "Ritual Summon" effects |
| `aux.AddEquipProcedure(c[,player,filter,eqlimit,cost,tg,op,con])` | Equip Spells |
| `aux.AddPersistentProcedure(...)` | Continuous Traps that target a card persistently |
| `Gemini.AddProcedure(c)`, `Spirit.AddProcedure(c,EVENT_SUMMON_SUCCESS,...)`, `aux.AddUnionProcedure(c,f)` | Gemini / Spirit / Union |

## 10. Constants by family

| Family | File | Examples |
|---|---|---|
| Locations | `constant.lua` | `LOCATION_DECK HAND MZONE SZONE GRAVE REMOVED EXTRA OVERLAY ONFIELD FZONE PZONE STZONE MMZONE EMZONE` |
| Positions | `constant.lua` | `POS_FACEUP_ATTACK FACEDOWN_DEFENSE FACEUP FACEDOWN ATTACK DEFENSE` |
| Card types | `constant.lua` | `TYPE_MONSTER SPELL TRAP NORMAL EFFECT FUSION RITUAL SYNCHRO XYZ LINK PENDULUM TUNER FLIP TOKEN QUICKPLAY CONTINUOUS EQUIP FIELD COUNTER ...` |
| Attributes / races | `constant.lua` | `ATTRIBUTE_LIGHT ...`, `RACE_BEASTWARRIOR` (no underscore), `RACE_WINGEDBEAST`, `RACE_SEASERPENT` |
| Reasons | `constant.lua` | `REASON_EFFECT COST DESTROY BATTLE DISCARD RELEASE MATERIAL SYNCHRO XYZ LINK FUSION RITUAL REPLACE RULE` |
| Effect types / flags / codes / events / categories | `constant.lua` | see 02 and 07 |
| Resets | `constant.lua` | `RESET_EVENT RESET_PHASE RESET_CHAIN RESETS_STANDARD RESETS_STANDARD_PHASE_END RESETS_REDIRECT` |
| Hints | `constant.lua` | `HINT_SELECTMSG`, `HINTMSG_*`, `TIMING_*`, `TIMINGS_CHECK_MONSTER(_E)` |
| Archetypes | `archetype_setcode_constants.lua` | `SET_*` (615) |
| Card names, counters | `card_counter_constants.lua` | `CARD_*`, `COUNTER_*` |

Common mistakes the linter found in upstream scripts: `RACE_BEAST_WARRIOR` (should be
`RACE_BEASTWARRIOR`), `SET_HORUS_BLACK_FLAME_DRAGON` (should be
`SET_HORUS_THE_BLACK_FLAME_DRAGON`), `:IsController()` (should be `:IsControler()`),
`Group.NewGroup()` (should be `Group.CreateGroup()`).
