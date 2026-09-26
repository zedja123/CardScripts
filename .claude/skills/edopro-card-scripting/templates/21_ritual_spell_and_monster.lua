--(Japanese name)
--Template: Ritual Spell (the Ritual Monster itself only needs c:EnableReviveLimit())
--PSCT: This card can be used to Ritual Summon any "Archetype" Ritual Monster. You must also Tribute monsters from your hand or field whose total Levels equal or exceed the Level of the Ritual Monster you Ritual Summon.
--NOTE: Ritual.AddProcGreater / AddProcEqual register and return the activation; the Ritual Monster only needs c:EnableReviveLimit().
local s,id=GetID()
function s.initial_effect(c)
	--Ritual Summon any "Archetype" Ritual Monster, Tributing monsters whose total Levels equal or exceed its Level
	local e1=Ritual.AddProcGreater({handler=c,filter=aux.FilterBoolFunction(Card.IsSetCard,SET_ARCHETYPE)})
	e1:SetDescription(aux.Stringid(id,0))
end
s.listed_series={SET_ARCHETYPE}
