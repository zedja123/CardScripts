--(Japanese name)
--Template: Fusion Spell
--PSCT: Fusion Summon 1 "Archetype" Fusion Monster from your Extra Deck, using monsters from your hand or field as material.
--NOTE: Fusion.CreateSummonEff takes a named-parameter table (fusfilter, matfilter, extrafil, extraop, stage2, ...).
local s,id=GetID()
function s.initial_effect(c)
	--Fusion Summon 1 "Archetype" Fusion Monster from your Extra Deck, using monsters from your hand or field as material
	local e1=Fusion.CreateSummonEff({handler=c,fusfilter=aux.FilterBoolFunction(Card.IsSetCard,SET_ARCHETYPE)})
	e1:SetDescription(aux.Stringid(id,0))
	c:RegisterEffect(e1)
end
s.listed_series={SET_ARCHETYPE}
