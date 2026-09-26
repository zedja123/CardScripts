--(Japanese name)
--Template: Quick Effect from the hand, negate the activation
--PSCT: When your opponent activates a card or effect (Quick Effect): You can discard this card; negate the activation, and if you do, destroy that card. You can only use this effect of "Template" once per turn.
--NOTE: EVENT_CHAINING: eg = the activated card, ev = its chain link, re = the effect, rp = its player.
--NOTE: DAMAGE_STEP+DAMAGE_CAL flags: chain responses are usually legal in the Damage Step.
--NOTE: Destroy only if the card is still related to its own effect (it may have left the field).
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
