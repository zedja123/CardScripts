--(Japanese name)
--Template: Equip Spell
--PSCT: Equip only to a Warrior monster. It gains 700 ATK. If the equipped monster destroys an opponent's monster by battle: You can draw 1 card.
--NOTE: aux.AddEquipProcedure registers the activation, targeting and equip limit.
--NOTE: EFFECT_TYPE_EQUIP effects apply to the equipped monster.
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
