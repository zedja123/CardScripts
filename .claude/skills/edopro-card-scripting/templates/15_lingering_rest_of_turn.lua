--(Japanese name)
--Template: Lingering player effect applied on resolution ("for the rest of this turn")
--PSCT: Draw 2 cards, also for the rest of this turn, you cannot activate monster effects, except "Archetype" monsters'.
--NOTE: Lingering player effects are registered on resolution with RESET_PHASE|PHASE_END.
--NOTE: EFFECT_FLAG_CLIENT_HINT + description shows the restriction to the player.
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
