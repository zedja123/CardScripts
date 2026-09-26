--(Japanese name)
--Template: Link Monster
--PSCT: 2+ Effect Monsters / Monsters this card points to cannot be destroyed by battle.
--NOTE: Link.AddProcedure(c,filter,min[,max,group_check]); the Link Rating comes from the database.
local s,id=GetID()
function s.initial_effect(c)
	c:EnableReviveLimit()
	--Link Summon procedure: 2+ Effect Monsters
	Link.AddProcedure(c,aux.FilterBoolFunctionEx(Card.IsType,TYPE_EFFECT),2)
	--Monsters this card points to cannot be destroyed by battle
	local e1=Effect.CreateEffect(c)
	e1:SetType(EFFECT_TYPE_FIELD)
	e1:SetCode(EFFECT_INDESTRUCTABLE_BATTLE)
	e1:SetRange(LOCATION_MZONE)
	e1:SetTargetRange(LOCATION_MZONE,LOCATION_MZONE)
	e1:SetTarget(function(e,c) return e:GetHandler():GetLinkedGroup():IsContains(c) end)
	e1:SetValue(1)
	c:RegisterEffect(e1)
end
