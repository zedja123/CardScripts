--(Japanese name)
--Template: Pendulum Monster with a Pendulum Effect
--PSCT: [Pendulum Effect] Once per turn: You can target 1 "Archetype" monster you control; it gains 300 ATK until the end of this turn. [Monster Effect] ...
--NOTE: Pendulum.AddProcedure(c) adds both the Pendulum Summon and the activation in the Pendulum Zone.
--NOTE: Pendulum Effects use SetRange(LOCATION_PZONE).
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
