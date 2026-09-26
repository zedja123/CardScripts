"""Rule checks for duels run with duelsim.py (used by explore.py and scenario.py).

An observer written in Lua is registered inside the duel (global continuous effects), so
activations, resolutions and Special Summons are recorded with the engine's own view of
the cards (current race/attribute, summon player, summon location). The checks then look
for violations of usage limits and of summon/activation locks.
"""
from __future__ import annotations

import re
from functools import lru_cache

from duelsim import find_script

OBSERVER = r"""
local function log(s) Debug.Message('EV|'..s) end
local function T() return Duel.GetTurnCount() end
local function setflags(c)
  local f=0
  if c:IsSetCard(0xe02) then f=f|1 end
  if c:IsSetCard(0x1e04) then f=f|2 end
  if c:IsSetCard(0xe03) then f=f|4 end
  return f
end
local function faceup_code(p,code,eg,both)
  return Duel.IsExistingMatchingCard(function(x) return x:IsFaceup() and x:IsCode(code) and not eg:IsContains(x) end,
    p,LOCATION_MZONE,both and LOCATION_MZONE or 0,1,nil)
end
local g1=Effect.GlobalEffect()
g1:SetType(EFFECT_TYPE_FIELD+EFFECT_TYPE_CONTINUOUS)
g1:SetCode(EVENT_CHAINING)
g1:SetOperation(function(e,tp,eg,ep,ev,re,r,rp)
  local h=re:GetHandler()
  log('CH|'..T()..'|'..rp..'|'..re:GetDescription()..'|'..ev..'|'..h:GetCode()..'|'..(re:IsMonsterEffect() and 1 or 0)..'|'..h:GetAttribute()..'|'..Duel.GetCurrentPhase())
end)
Duel.RegisterEffect(g1,0)
local g2=g1:Clone()
g2:SetCode(EVENT_CHAIN_SOLVED)
g2:SetOperation(function(e,tp,eg,ep,ev,re,r,rp)
  log('SV|'..T()..'|'..rp..'|'..re:GetDescription()..'|'..ev)
end)
Duel.RegisterEffect(g2,0)
local g3=g1:Clone()
g3:SetCode(EVENT_CHAIN_NEGATED)
g3:SetOperation(function(e,tp,eg,ep,ev,re,r,rp) log('NA|'..T()..'|'..ev) end)
Duel.RegisterEffect(g3,0)
local g4=g1:Clone()
g4:SetCode(EVENT_CHAIN_DISABLED)
g4:SetOperation(function(e,tp,eg,ep,ev,re,r,rp) log('NG|'..T()..'|'..ev) end)
Duel.RegisterEffect(g4,0)
local g6=g1:Clone()
g6:SetCode(EVENT_CHAIN_SOLVING)
g6:SetOperation(function(e,tp,eg,ep,ev,re,r,rp) log('SL|'..T()..'|'..ev) end)
Duel.RegisterEffect(g6,0)
local g5=g1:Clone()
g5:SetCode(EVENT_SPSUMMON_SUCCESS)
g5:SetOperation(function(e,tp,eg,ep,ev,re,r,rp)
  for c in eg:Iter() do
    local sp=c:GetSummonPlayer()
    local kur=faceup_code(sp,271000004,eg,false) and 1 or 0
    local king=faceup_code(sp,270000210,eg,true) and 1 or 0
    log('SS|'..T()..'|'..sp..'|'..c:GetCode()..'|'..c:GetRace()..'|'..c:GetAttribute()..'|'..c:GetSummonLocation()..'|'..setflags(c)..'|'..kur..'|'..king..'|'..c:GetSummonType())
  end
end)
Duel.RegisterEffect(g5,0)
"""

RACE_ZOMBIE = 0x10
ATTR_FIRE = 0x4
LOC_HAND, LOC_EXTRA = 0x02, 0x40

# Summon/activation locks of the custom cards, checked on every duel. Add an entry when a new
# card says "you cannot Special Summon ... except ..." (see the kinds handled in check()).
# locks applied when the effect (owner code, string index) resolves without being negated
RESOLVE_LOCKS = {
	(270000201, 0): ("zombie", False),
	(270000203, 0): ("zombie", False),
	(270000204, 0): ("zombie", False),
	(270000207, 0): ("zombie", True),     # "and if you do": only if the summon happened
	(270000401, 0): ("buildrider", False),
	(271000002, 0): ("fire_monster_effects", True),
}
# locks that cover the whole turn in which the effect is activated (cost-time locks)
ACTIVATE_LOCKS = {
	(270000301, 0): "lavoisier_extra",
	(270000301, 1): "lavoisier_extra",
}

@lru_cache(maxsize=None)
def count_limits(code: int) -> dict[int, tuple]:
	"""string index -> (counter key, kind) for effects with a code-based count limit."""
	path = find_script(f"c{code}.lua")
	if path is None:
		return {}
	effs: dict[str, dict] = {}
	all_effs: list[dict] = []
	for line in open(path, encoding="utf-8"):
		m = re.match(r"\s*local (\w+)=Effect\.CreateEffect\(", line)
		if m:
			effs[m.group(1)] = {}
			all_effs.append(effs[m.group(1)])
			continue
		m = re.match(r"\s*local (\w+)=(\w+):Clone\(\)", line)
		if m:
			effs[m.group(1)] = dict(effs.get(m.group(2), {}))
			all_effs.append(effs[m.group(1)])
			continue
		m = re.match(r"\s*(\w+):SetDescription\(aux\.Stringid\(id,(\d+)\)\)", line)
		if m and m.group(1) in effs:
			effs[m.group(1)]["desc"] = int(m.group(2))
			continue
		m = re.match(r"\s*(\w+):SetCountLimit\((.*)\)\s*$", line)
		if m and m.group(1) in effs:
			effs[m.group(1)]["count"] = m.group(2)
		m = re.match(r"\s*(\w+):SetType\((.*)\)\s*$", line)
		if m and m.group(1) in effs:
			effs[m.group(1)]["type"] = m.group(2)
	out = {}
	for v in all_effs:
		if "desc" not in v or "count" not in v:
			continue
		if "SPSUMMON_PROC" in v.get("type", "") or "CONTINUOUS" in v.get("type", ""):
			continue
		args = v["count"]
		kind = "duel" if "COUNT_CODE_DUEL" in args else ("oath" if "COUNT_CODE_OATH" in args else "turn")
		m = re.match(r"1,\s*\{id,(\d+)\}", args) or re.match(r"1,\s*id\b", args)
		if not m:
			continue  # soft limit (per copy): not checked
		key = int(m.group(1)) if m.groups() else 0
		out[v["desc"]] = (key, kind)
	return out

def parse_events(lines: list[str]) -> list[list]:
	out = []
	for l in lines:
		if l.startswith("EV|"):
			out.append(l.split("|")[1:])
	return out

def check(lines: list[str], custom: set[int]) -> list[str]:
	ev = parse_events(lines)
	problems = []
	# ---- usage limits
	used: dict[tuple, int] = {}
	# activations whose activation was negated: OATH limits are refunded by the engine (ruling)
	negated_act = set()
	last_ch: dict[int, int] = {}
	for i, e in enumerate(ev):
		if e[0] == "CH":
			last_ch[int(e[4])] = i
		elif e[0] == "NA" and int(e[2]) in last_ch:
			negated_act.add(last_ch[int(e[2])])
	for i, e in enumerate(ev):
		if e[0] != "CH":
			continue
		turn, rp, desc = int(e[1]), int(e[2]), int(e[3])
		owner, idx = desc >> 20, desc & 0xFFFFF
		if owner not in custom:
			continue
		lim = count_limits(owner).get(idx)
		if not lim:
			continue
		key, kind = lim
		if kind == "oath" and i in negated_act:
			continue
		k = (rp, owner, key, "duel" if kind == "duel" else turn)
		used[k] = used.get(k, 0) + 1
		if used[k] == 2:
			problems.append(f"LIMIT: {owner} effect str{idx} (counter {key}, once per {kind}) activated twice by player {rp} (turn {turn})")
	# ---- locks
	chain: dict[int, dict] = {}
	active: list[tuple] = []  # (player, turn, kind)
	solving = None
	for i, e in enumerate(ev):
		tag = e[0]
		if tag == "CH":
			turn, rp, desc, ct = int(e[1]), int(e[2]), int(e[3]), int(e[4])
			chain[ct] = dict(desc=desc, rp=rp, turn=turn, negated=False, ss=False)
			key = (desc >> 20, desc & 0xFFFFF)
			if key in ACTIVATE_LOCKS:
				active.append((rp, turn, ACTIVATE_LOCKS[key], "whole"))
			# activation locks: monster effects of non-FIRE monsters
			ismon, attr, hcode = int(e[6]), int(e[7]), int(e[5])
			for (p, t, kind, _) in active:
				if kind == "fire_monster_effects" and p == rp and t == turn and ismon and not attr & ATTR_FIRE:
					problems.append(f"LOCK fire_monster_effects: player {rp} activated a non-FIRE monster effect ({hcode}) on turn {turn}")
		elif tag == "SL":
			solving = int(e[2])
		elif tag in ("NG", "NA"):
			ct = int(e[2])
			if ct in chain:
				chain[ct]["negated"] = True
		elif tag == "SS":
			turn, sp, code, race, attr, sloc, flags, kur, king = (int(x) for x in e[1:10])
			if solving in chain:
				chain[solving]["ss"] = True
			for (p, t, kind, scope) in active:
				if p != sp or t != turn:
					continue
				if kind == "zombie" and not race & RACE_ZOMBIE:
					problems.append(f"LOCK zombie: player {sp} Special Summoned non-Zombie {code} on turn {turn}")
				if kind == "buildrider" and not flags & 2:
					problems.append(f"LOCK buildrider: player {sp} Special Summoned non-Build Rider {code} on turn {turn}")
				if kind == "lavoisier_extra" and sloc & LOC_EXTRA and not flags & 4:
					problems.append(f"LOCK lavoisier_extra: player {sp} Special Summoned non-Lavoisier {code} from the Extra Deck on turn {turn}")
			if kur and not attr & ATTR_FIRE:
				problems.append(f"LOCK Kuranix: player {sp} Special Summoned non-FIRE {code} while controlling Kuranix (turn {turn})")
			if king and sloc & LOC_HAND and not race & RACE_ZOMBIE:
				problems.append(f"LOCK King: player {sp} Special Summoned non-Zombie {code} from the hand while The True Ashens - King was on the field (turn {turn})")
		elif tag == "SV":
			ct = int(e[4])
			c = chain.get(ct)
			if not c:
				continue
			key = (c["desc"] >> 20, c["desc"] & 0xFFFFF)
			if key in RESOLVE_LOCKS and not c["negated"]:
				kind, needs_ss = RESOLVE_LOCKS[key]
				if not needs_ss or c["ss"]:
					active.append((c["rp"], c["turn"], kind, "after"))
			solving = None
			if ct == 1:
				chain.clear()
	# whole-turn locks also forbid summons earlier in the turn
	for (p, t, kind, scope) in active:
		if scope != "whole":
			continue
		for e in ev:
			if e[0] == "SS" and int(e[1]) == t and int(e[2]) == p and int(e[6]) & LOC_EXTRA and not int(e[7]) & 4:
				problems.append(f"LOCK lavoisier_extra (earlier in turn): player {p} Special Summoned non-Lavoisier {e[3]} from the Extra Deck on turn {t}")
	return sorted(set(problems))
