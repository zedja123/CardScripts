--(Japanese name)
--Template: Inherent Special Summon procedure (does not start a Chain)
--PSCT: If you control an "Archetype" monster, you can Special Summon this card (from your hand). You can only Special Summon "Template" once per turn this way.
--NOTE: Inherent summons do not use the Chain; condition(e,c) with c==nil means 'is the procedure available'.
--NOTE: 'once per turn this way' = SetCountLimit(1,id,EFFECT_COUNT_CODE_OATH) on the procedure.
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
