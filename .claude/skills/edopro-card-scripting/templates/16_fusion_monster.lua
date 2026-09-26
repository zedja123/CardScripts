--(Japanese name)
--Template: Fusion Monster
--PSCT: 1 "Archetype" monster + 1 LIGHT monster / If this card is Fusion Summoned: You can target 1 card on the field; destroy it.
--NOTE: Fusion.AddProcMix(c,sub,insf,...): sub = Fusion Substitute monsters allowed; insf = the check passes when an effect summons it without a material group. (true,true) in 338 of 359 official uses; (false,false) for cards that forbid substitutes.
--NOTE: material_setcode lets archetype-material checks see the Fusion Monster.
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
