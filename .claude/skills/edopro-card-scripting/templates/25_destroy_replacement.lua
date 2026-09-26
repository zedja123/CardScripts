--(Japanese name)
--Template: Destruction replacement from the GY
--PSCT: If an "Archetype" monster you control would be destroyed by battle or card effect, you can banish this card from your GY instead.
--NOTE: Replacement effects are FIELD+CONTINUOUS (not activated): target returns whether to replace, value selects the protected cards.
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
