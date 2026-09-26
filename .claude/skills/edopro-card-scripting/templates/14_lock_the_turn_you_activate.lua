--(Japanese name)
--Template: Summon restriction tied to activation ("the turn you activate this effect")
--PSCT: You can Tribute this card; Special Summon 1 "Archetype" monster from your Deck. You cannot Special Summon monsters from the Extra Deck, except "Archetype" monsters, the turn you activate this effect. You can only use this effect of "Template" once per turn.
--NOTE: The lock is created in the cost with EFFECT_FLAG_OATH so that it disappears if the activation is negated.
--NOTE: The activity counter makes the effect unusable if a forbidden summon already happened this turn.
--NOTE: aux.addTempLizardCheck informs 'Clock Lizard'-type effects of the Extra Deck restriction.
--NOTE: GetMZoneCount(tp,c) because Tributing this card frees its zone.
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
