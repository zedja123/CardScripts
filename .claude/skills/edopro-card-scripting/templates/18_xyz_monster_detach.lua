--(Japanese name)
--Template: Xyz Monster with a detach cost
--PSCT: 2 Level 4 monsters / Once per turn (Quick Effect): You can detach 1 material from this card; this card gains 1000 ATK until the end of this turn.
--NOTE: Xyz.AddProcedure(c,filter,level,count[,alternative,desc,max_count,...]).
--NOTE: Stat changes usable in the Damage Step need EFFECT_FLAG_DAMAGE_STEP and aux.StatChangeDamageStepCondition.
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
