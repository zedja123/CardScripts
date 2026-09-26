#!/usr/bin/env python3
"""Scenario tests for the ZedjaCustomCards cards on ygopro-core.

  scenarios_custom.py                 # run every test
  scenarios_custom.py kiryu_counts_as_two_link_materials ...

Each test builds a board, plays exact moves and asserts the outcome; engine errors and the
rule checks of duelcheck.py fail a test too. Add a test when a card is scripted or fixed,
especially for procedures and continuous effects, which random exploration cannot verify.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenario import (Act, Answer, Phase, Pick, Summon, activatable, begin, card, desc_of,  # noqa: E402
                      expect, filler, lua_bool, lua_val, new_duel, play, prompts, run_tests, test)

BE, DM = 89631139, 46986414
POT, MST, RAIGEKI, DARK_HOLE, REBORN = 55144522, 5318639, 12580477, 53129443, 83764718

# ---------------------------------------------------------------- fixes from the review
@test
def sphere_field_not_activatable_without_lavoisier_monster():
	d = new_duel()
	d.add(270000308, 0, "hand"); filler(d, 0); filler(d, 1)
	begin(d)
	acts = activatable(d)
	expect(all(c != 270000308 for c, _ in acts), f"Sphere Field activatable with no Lavoisier monster in the Deck: {acts}")
	return d

@test
def sphere_field_adds_lavoisier_monster():
	d = new_duel()
	d.add(270000308, 0, "hand"); d.add(270000301, 0, "deck"); filler(d, 0); filler(d, 1)
	begin(d)
	play(d, [Act(270000308, 0), Pick(270000301)])
	expect(270000301 in d.codes(0, "hand"), "Lavoisier Proust not added")
	expect(lua_bool(d, card(270000308, 0, "LOCATION_FZONE") + "~=nil"), "Sphere Field not in the Field Zone")
	return d

def vilecoil_board(extra_banished):
	d = new_duel()
	d.lua("""
local c=Debug.AddCard(270000111,0,0,LOCATION_MZONE,2,POS_FACEUP_ATTACK,true)
Debug.AddCard(270000101,0,0,LOCATION_MZONE,2,POS_FACEUP_ATTACK)
Debug.AddCard(270000103,0,0,LOCATION_MZONE,2,POS_FACEUP_ATTACK)
Debug.PreSummon(c,SUMMON_TYPE_XYZ)
""", "setup.lua")
	d.add(270000102, 0, "removed")          # Wiccanthrope Road (Set by the effect)
	for c in extra_banished:
		d.add(c, 0, "removed")
	d.add(POT, 0, "hand")                    # a Spell to banish
	filler(d, 0); filler(d, 1)
	return d

@test
def vilecoil_does_not_offer_useless_banish():
	d = vilecoil_board([])
	begin(d)
	play(d, [Act(270000111, 1), Pick(270000101), Pick(270000102)])
	expect(not prompts(d, "SELECT_YESNO", desc_of(270000111, 3)), "banish offered with no Wiccanthrope Spell to return")
	st = d.state()
	expect(any(c["code"] == 270000102 for c in st[(0, "szone")]), "Wiccanthrope Road was not Set")
	expect(POT in d.codes(0, "hand"), "Spell left the hand")
	return d

@test
def vilecoil_banish_and_return():
	d = vilecoil_board([270000106])       # Wiccanthrope Reason also banished
	begin(d)
	play(d, [Act(270000111, 1), Pick(270000101), Pick(270000102), Answer(True, desc_of(270000111, 3)), Pick(POT), Pick(270000106)])
	expect(270000106 in d.codes(0, "grave"), "Wiccanthrope Reason not returned to the GY")
	expect(POT in d.codes(0, "removed"), "Pot of Greed not banished")
	return d

@test
def build_rider_extra_attributes_only_on_field():
	d = new_duel()
	cases = {270000410: "ATTRIBUTE_WIND", 270000411: "ATTRIBUTE_EARTH", 270000413: "ATTRIBUTE_FIRE",
	         270000414: "ATTRIBUTE_DARK", 270000415: "ATTRIBUTE_DARK", 270000412: "ATTRIBUTE_WATER"}
	for i, code in enumerate(cases):
		d.add(code, 0, "grave")
	filler(d, 0); filler(d, 1)
	begin(d)
	for code, attr in cases.items():
		expect(not lua_bool(d, card(code, 0, "LOCATION_GRAVE") + f":IsAttribute({attr})"),
		       f"{code} has its extra Attribute in the GY")
	d2 = new_duel()
	for i, code in enumerate(cases):
		d2.lua(f"Debug.AddCard({code},0,0,LOCATION_MZONE,{i},POS_FACEUP_ATTACK,true)", "setup.lua")
	filler(d2, 0); filler(d2, 1)
	begin(d2)
	for code, attr in cases.items():
		expect(lua_bool(d2, card(code) + f":IsAttribute({attr})"), f"{code} lacks its extra Attribute on the field")
	return d2

@test
def cinder_token_summons_cleanly():
	d = new_duel()
	d.add(270000202, 0, "hand"); filler(d, 0); filler(d, 1)
	begin(d)
	play(d, [Act(270000202, 0), Answer(True, desc_of(270000202, 3))])
	expect(270000299 in d.codes(0, "mzone"), "Cinder Token not summoned")
	expect(lua_bool(d, card(270000299) + ":IsType(TYPE_NORMAL)"), "Cinder Token is not a Normal Monster")
	expect(lua_val(d, card(270000299) + ":GetAttack()") == "2000", "Cinder Token ATK")
	return d

# ---------------------------------------------------------------- effect never reached by exploration
@test
def youcan_pendulum_negates_response_and_summons_itself():
	d = new_duel()
	d.lua("""
Debug.AddCard(270000313,0,0,LOCATION_PZONE,0,POS_FACEUP_ATTACK,true)
Debug.AddCard(270000301,0,0,LOCATION_MZONE,0,POS_FACEUP_ATTACK,true)
Debug.AddCard(5318639,1,1,LOCATION_SZONE,0,POS_FACEDOWN_DEFENSE)
""", "setup.lua")
	d.add(270000308, 0, "hand"); d.add(270000304, 0, "deck"); filler(d, 0); filler(d, 1)
	begin(d)
	# activate Sphere Field; the opponent responds with MST on it; YOUCAN negates MST
	play(d, [Act(270000308, 0), Act(MST, player=1), Pick(270000308, player=1),
	         Act(270000313, 0), Pick(270000301), Pick(MST), Pick(270000304)])
	st = d.state()
	expect(270000313 in [c["code"] for c in st[(0, "mzone")]], "YOUCAN not Special Summoned")
	expect(MST in d.codes(1, "grave"), "MST not negated/destroyed")
	expect(270000304 in d.codes(0, "hand"), "Sphere Field did not resolve")
	return d

# ---------------------------------------------------------------- intricate mechanics
@test
def kiryu_counts_as_two_link_materials():
	d = new_duel()
	d.lua("Debug.AddCard(270000402,0,0,LOCATION_MZONE,2,POS_FACEUP_ATTACK,true)", "setup.lua")
	d.add(270000411, 0, "extra"); filler(d, 0); filler(d, 1)
	begin(d)
	play(d, [Summon(270000411)])
	expect(270000411 in d.codes(0, "mzone"), "Hawk Gatling not Link Summoned with Kiryu alone")
	expect(270000402 in d.codes(0, "grave"), "Kiryu not used as material")
	expect(lua_bool(d, card(270000411) + ":IsLinkSummoned()"), "not treated as a Link Summon")
	return d

@test
def kiryu_needs_no_other_monsters():
	d = new_duel()
	d.lua("""Debug.AddCard(270000402,0,0,LOCATION_MZONE,2,POS_FACEUP_ATTACK,true)
Debug.AddCard(89631139,0,0,LOCATION_MZONE,1,POS_FACEUP_ATTACK,true)""", "setup.lua")
	d.add(270000411, 0, "extra"); filler(d, 0); filler(d, 1)
	begin(d)
	sp = [x["code"] for x in d.pending.data["spsummon"]]
	expect(270000411 not in sp, "Hawk Gatling summonable although another monster is controlled")
	return d

@test
def true_ashens_king_uses_spell_zone_zombie():
	d = new_duel()
	d.lua("""
Debug.AddCard(270000203,0,0,LOCATION_MZONE,0,POS_FACEUP_ATTACK,true)
Debug.AddCard(270000203,0,0,LOCATION_MZONE,1,POS_FACEUP_ATTACK,true)
Debug.AddCard(270000204,0,0,LOCATION_MZONE,2,POS_FACEUP_ATTACK,true)
local s=Debug.AddCard(270000206,0,0,LOCATION_SZONE,1,POS_FACEUP_ATTACK)
local e1=Effect.CreateEffect(s)
e1:SetType(EFFECT_TYPE_SINGLE)
e1:SetProperty(EFFECT_FLAG_CANNOT_DISABLE)
e1:SetCode(EFFECT_CHANGE_TYPE)
e1:SetValue(TYPE_SPELL|TYPE_CONTINUOUS)
e1:SetReset((RESET_EVENT|RESETS_STANDARD)&~RESET_TURN_SET)
s:RegisterEffect(e1)
""", "setup.lua")
	d.add(270000210, 0, "extra"); filler(d, 0); filler(d, 1)
	begin(d)
	sp = [x["code"] for x in d.pending.data["spsummon"]]
	expect(270000210 in sp, f"The True Ashens - King not summonable: {sp}")
	play(d, [Summon(270000210), Pick((270000206, "szone"), 270000203, 270000203, 270000204)])
	expect(270000210 in d.codes(0, "mzone"), "King not Link Summoned")
	expect(270000206 in d.codes(0, "grave"), "Spell & Trap Zone Zombie not used as material")
	return d

@test
def milacresy_link_as_tuner_for_ceronius():
	d = new_duel()
	d.lua("""
Debug.AddCard(270000509,0,0,LOCATION_MZONE,5,POS_FACEUP_ATTACK,true)
Debug.AddCard(270000505,0,0,LOCATION_MZONE,0,POS_FACEUP_ATTACK,true)
Debug.AddCard(270000502,0,0,LOCATION_MZONE,1,POS_FACEUP_ATTACK,true)
""", "setup.lua")
	d.add(270000513, 0, "extra"); filler(d, 0); filler(d, 1)
	begin(d)
	sp = [x["code"] for x in d.pending.data["spsummon"]]
	expect(270000513 in sp, f"Ceronius not Synchro Summonable with a Link Monster as Tuner: {sp}")
	play(d, [Summon(270000513), Pick(270000509), Pick(270000505, 270000502)])
	expect(270000513 in d.codes(0, "mzone"), "Ceronius not summoned")
	expect(set([270000509, 270000505, 270000502]) <= set(d.codes(0, "grave")), "materials not in the GY")
	return d

@test
def kuranix_from_hand_gains_destroyed_atk():
	d = new_duel()
	d.lua("Debug.AddCard(69000994,0,0,LOCATION_MZONE,2,POS_FACEUP_ATTACK,true)", "setup.lua")  # Fire King Avatar Barong 1800
	d.add(271000004, 0, "hand"); d.add(RAIGEKI, 1, "hand"); filler(d, 0); filler(d, 1)
	begin(d)
	play(d, [Phase("ep"), Act(RAIGEKI, player=1), Act(271000004)], stop="idle", player=1)
	expect(271000004 in d.codes(0, "mzone"), "Kuranix not Special Summoned")
	atk = int(lua_val(d, card(271000004) + ":GetAttack()"))
	expect(atk == 1800, f"Kuranix ATK {atk}, expected 1800")
	return d

@test
def chaos_puppet_form_rank_up():
	d = new_duel()
	d.add(272000005, 0, "hand"); d.add(48995978, 0, "extra"); d.add(6165656, 0, "extra"); filler(d, 0); filler(d, 1)
	begin(d)
	play(d, [Act(272000005, 0), Pick(48995978), Pick(6165656)])
	st = d.state()
	mz = {c["code"]: c for c in st[(0, "mzone")]}
	expect(6165656 in mz, "Number C88 not summoned")
	expect(mz[6165656]["overlay"] == 1, f"C88 materials: {mz[6165656]['overlay']}")
	expect(lua_bool(d, card(6165656) + ":IsXyzSummoned()"), "C88 not treated as an Xyz Summon")
	return d

@test
def stop_replaces_destruction_from_gy():
	d = new_duel()
	d.lua("Debug.AddCard(270000301,0,0,LOCATION_MZONE,2,POS_FACEUP_ATTACK,true)", "setup.lua")
	d.add(270000309, 0, "grave"); d.add(DARK_HOLE, 0, "hand"); filler(d, 0); filler(d, 1)
	begin(d)
	play(d, [Act(DARK_HOLE), Answer(True)])
	expect(270000301 in d.codes(0, "mzone"), "Lavoisier Proust destroyed despite S.T.O.P.")
	expect(270000309 in d.codes(0, "removed"), "S.T.O.P. not banished")
	return d

@test
def walioright_excludes_banished_cost():
	d = new_duel()
	d.lua("Debug.AddCard(270000104,0,0,LOCATION_MZONE,2,POS_FACEUP_ATTACK,true)", "setup.lua")
	d.add(270000102, 0, "grave"); d.add(POT, 0, "grave"); d.add(BE, 0, "grave"); filler(d, 0); filler(d, 1)
	begin(d)
	play(d, [Act(270000104, 2), Pick(270000102), Pick(POT, BE)])
	sel = [m for m in d.messages if m.name == "SELECT_CARD" and m.player == 0]
	last = sel[-1].data["cards"]
	expect(270000102 not in [c["code"] for c in last], "the banished cost card was offered")
	expect(270000102 in d.codes(0, "removed"), "cost not banished")
	expect(POT not in d.codes(0, "grave") and BE not in d.codes(0, "grave"), "cards not shuffled")
	return d

@test
def party_assemble_stats():
	d = new_duel()
	d.lua("""
Debug.AddCard(270000113,0,0,LOCATION_SZONE,0,POS_FACEUP_ATTACK)
Debug.AddCard(89631139,0,0,LOCATION_MZONE,0,POS_FACEUP_ATTACK,true)
Debug.AddCard(46986414,0,0,LOCATION_MZONE,1,POS_FACEUP_ATTACK,true)
Debug.AddCard(89631139,0,0,LOCATION_MZONE,2,POS_FACEUP_ATTACK,true)
""", "setup.lua")
	filler(d, 0); filler(d, 1)
	begin(d)
	# Types: Dragon, Spellcaster (2); Attributes: LIGHT, DARK (2) -> +200
	atk = int(lua_val(d, card(46986414) + ":GetAttack()"))
	expect(atk == 2700, f"Dark Magician ATK {atk}, expected 2700")
	return d

@test
def ornstein_places_destroyed_monster_as_spell():
	d = new_duel()
	d.add(270000205, 0, "grave"); d.add(REBORN, 0, "hand"); filler(d, 0); filler(d, 1)
	d.lua("Debug.AddCard(89631139,1,1,LOCATION_MZONE,0,POS_FACEUP_ATTACK,true)", "setup.lua")
	begin(d)
	play(d, [Act(REBORN), Pick(270000205), Act(270000205, 1), Pick(BE), Answer(True, desc_of(270000205, 3))])
	st = d.state()
	expect(any(c["code"] == BE for c in st[(1, "szone")]), "Blue-Eyes not placed in its owner's Spell & Trap Zone")
	expect(lua_bool(d, card(BE, 1, "LOCATION_SZONE") + ":IsType(TYPE_SPELL+TYPE_CONTINUOUS)"), "not a Continuous Spell")
	return d

@test
def skill_revolution_des_fleurs():
	d = new_duel()
	d.add(27999999, 0, "deck")
	for _ in range(6):
		d.add(36405256, 0, "deck")
	d.add(48421595, 0, "deck")
	for _ in range(3):
		d.add(36405256, 0, "hand")
	d.add(BE, 0, "hand")
	filler(d, 1)
	begin(d)
	summ = [x["code"] for x in d.pending.data["summon"]]
	expect(36405256 in summ, f"Sorciere de Fleur cannot be Normal Summoned without Tributes: {summ}")
	acts = activatable(d)
	expect(any(c == 27999999 for c, _ in acts) or d.pending.data["activate"], f"skill effects not offered: {acts}")
	return d

# ---------------------------------------------------------------- built-in summoning procedures
def spsummonable(d):
	return [(x["code"], x["loc"]) for x in d.pending.data["spsummon"]]

def proc_case(setup_lua, extra=(), hand=(), grave=(), battle=False):
	d = new_duel(first_turn_battle=battle)
	if setup_lua:
		d.lua(setup_lua, "setup.lua")
	for c in extra: d.add(c, 0, "extra")
	for c in hand: d.add(c, 0, "hand")
	for c in grave: d.add(c, 0, "grave")
	filler(d, 0); filler(d, 1)
	begin(d)
	return d

def mz(code, seq, player=0, proc=True):
	return f"Debug.AddCard({code},{player},{player},LOCATION_MZONE,{seq},POS_FACEUP_ATTACK,{'true' if proc else 'false'})\n"

@test
def hand_procedures_follow_their_conditions():
	cases = [
		# (card, where, setup that allows it, setup that forbids it)
		(270000101, "hand", "", mz(89631139, 0)),
		(270000103, "grave", mz(270000101, 0), mz(270000103, 0)),
		(270000104, "hand", mz(270000101, 0), mz(270000104, 0)),
		(270000206, "hand", "", mz(89631139, 0)),
		(270000403, "hand", mz(270000401, 0), mz(270000401, 0) + mz(89631139, 1)),
		(270000404, "hand", mz(270000401, 0), ""),
		(270000501, "hand", mz(270000504, 0), mz(89631139, 0)),
	]
	for code, where, ok_lua, bad_lua in cases:
		kw = {where: [code]}
		d = proc_case(ok_lua, **kw)
		expect(any(c == code for c, _ in spsummonable(d)), f"{code} not summonable by its procedure when allowed")
		play(d, [Summon(code)])
		expect(code in d.codes(0, "mzone"), f"{code} procedure did not summon it")
		d.close()
		d = proc_case(bad_lua, **kw)
		expect(not any(c == code for c, _ in spsummonable(d)), f"{code} summonable by its procedure when not allowed")
		d.close()
	return None

@test
def artorias_gy_all_zombie_condition():
	# controls a monster, but every monster in the GY is a Zombie
	d = proc_case(mz(89631139, 0), hand=[270000206], grave=[270000203])
	expect(any(c == 270000206 for c, _ in spsummonable(d)), "Artorias not summonable when all GY monsters are Zombies")
	d.close()
	d = proc_case(mz(89631139, 0), hand=[270000206], grave=[270000203, 46986414])
	expect(not any(c == 270000206 for c, _ in spsummonable(d)), "Artorias summonable with a non-Zombie in the GY")
	return d

def xyz_on_field(code, mats, seq=2):
	s = f"local c=Debug.AddCard({code},0,0,LOCATION_MZONE,{seq},POS_FACEUP_ATTACK,true)\n"
	for m in mats:
		s += f"Debug.AddCard({m},0,0,LOCATION_MZONE,{seq},POS_FACEUP_ATTACK)\n"
	s += "Debug.PreSummon(c,SUMMON_TYPE_XYZ)\n"
	return s

@test
def alternative_xyz_summons_transfer_materials():
	for new, base, mats in ((270000110, 270000108, (270000101, 270000103)),
	                        (270000112, 270000109, (270000101, 270000104)),
	                        (272000002, 48995978, (39806198, 39806198))):
		d = proc_case(xyz_on_field(base, mats), extra=[new])
		expect(any(c == new for c, _ in spsummonable(d)), f"{new} not summonable on {base}")
		play(d, [Summon(new), Pick(base)])
		st = {c["code"]: c for c in d.state()[(0, "mzone")]}
		expect(new in st, f"{new} not Xyz Summoned")
		expect(st[new]["overlay"] == 3, f"{new} has {st[new]['overlay']} materials, expected 3")
		d.close()
	return None

@test
def rutherford_on_lavoisier_link_once_per_turn():
	d = proc_case(mz(270000311, 5) + mz(270000310, 0), extra=[270000314, 270000314])
	expect(any(c == 270000314 for c, _ in spsummonable(d)), "Rutherford not summonable on a Lavoisier Link Monster")
	play(d, [Summon(270000314), Pick(270000311)])
	expect(270000314 in d.codes(0, "mzone"), "Rutherford not summoned")
	sp = [c for c, _ in spsummonable(d)]
	expect(270000314 not in sp, "second Rutherford summonable with the Link Monster procedure in the same turn")
	return d

@test
def albaz_tributes_a_fusion_monster():
	d = proc_case(mz(44146295, 0), extra=[270000099])
	expect(any(c == 270000099 for c, _ in spsummonable(d)), "Albaz, the Fallen not summonable by Tributing a Fusion Monster")
	play(d, [Summon(270000099), Pick(44146295)])
	expect(lua_bool(d, "Duel.IsExistingMatchingCard(Card.IsOriginalCode,0,LOCATION_MZONE,0,1,nil,270000099)")
	       and 44146295 in d.codes(0, "grave"), "procedure failed")
	expect(lua_bool(d, "Duel.GetFirstMatchingCard(Card.IsOriginalCode,0,LOCATION_MZONE,0,nil,270000099):IsCode(68468459)"),
	       "name is not Fallen of Albaz on the field")
	return d

# ---------------------------------------------------------------- continuous effects
@test
def sulyvahn_protects_ashens_from_effects():
	d = proc_case(mz(270000207, 0) + mz(270000203, 1) + mz(89631139, 2), hand=[DARK_HOLE])
	play(d, [Act(DARK_HOLE)])
	mzc = d.codes(0, "mzone")
	expect(270000207 in mzc and 270000203 in mzc, f"Ashens monsters destroyed: {mzc}")
	expect(89631139 in d.codes(0, "grave"), "non-Ashens monster survived Dark Hole")
	return d

@test
def sperelfler_and_stormgnarl_count_banished_spells():
	d = new_duel()
	d.lua(xyz_on_field(270000110, (270000101,), 2) + xyz_on_field(270000112, (270000101,), 3) + mz(270000101, 0)
	      + mz(89631139, 0, player=1), "setup.lua")
	for c in (POT, 270000102, 270000106):   # 3 face-up banished Spells (2 of yours, 1 of the opponent)
		d.add(c, 0 if c != POT else 1, "removed")
	filler(d, 0); filler(d, 1)
	begin(d)
	roth = int(lua_val(d, card(270000101) + ":GetAttack()"))
	be = int(lua_val(d, card(89631139, 1) + ":GetAttack()"))
	expect(roth == 1100 + 900, f"Rothockear ATK {roth}, expected 2000 (+300 x 3)")
	expect(be == 3000 - 900, f"opponent Blue-Eyes ATK {be}, expected 2100 (-300 x 3)")
	return d

@test
def sky_wall_boost_from_battle_phase():
	d = proc_case("Debug.AddCard(270000408,0,0,LOCATION_FZONE,0,POS_FACEUP_ATTACK)\n" + mz(270000401, 0), battle=True)
	a0 = int(lua_val(d, card(270000401) + ":GetAttack()"))
	play(d, [Phase("bp")], stop="battle")
	a1 = int(lua_val(d, card(270000401) + ":GetAttack()"))
	expect(a0 == 1500 and a1 == 2000, f"Kazumi ATK main {a0} / battle {a1}, expected 1500 / 2000")
	return d

@test
def serenayi_boost_during_battle_phase():
	d = proc_case(mz(270000501, 0) + mz(270000504, 1) + "Debug.AddCard(270000507,0,0,LOCATION_SZONE,0,POS_FACEDOWN_DEFENSE)\n", battle=True)
	a0 = int(lua_val(d, card(270000504) + ":GetAttack()"))
	play(d, [Phase("bp")], stop="battle")
	a1 = int(lua_val(d, card(270000504) + ":GetAttack()"))
	# face-up Milacresy cards you control: Serenayi, Amarae (the Set Spell is face-down) -> +600
	expect(a0 == 1300 and a1 == 1900, f"Amarae ATK main {a0} / battle {a1}, expected 1300 / 1900")
	return d

@test
def youcan_goes_to_pendulum_zone_when_it_leaves():
	d = proc_case("local c=Debug.AddCard(270000313,0,0,LOCATION_MZONE,0,POS_FACEUP_ATTACK,true)\nDebug.PreSummon(c,SUMMON_TYPE_FUSION)\n",
	              hand=[DARK_HOLE])
	play(d, [Act(DARK_HOLE)])
	expect(lua_bool(d, card(270000313, 0, "LOCATION_PZONE") + "~=nil"), f"YOUCAN not placed in the Pendulum Zone: {d.state()[(0,'szone')]}")
	return d

@test
def sparkling_untargetable_and_battle_phase_lock():
	setup = ("local c=Debug.AddCard(270000413,0,0,LOCATION_MZONE,0,POS_FACEUP_ATTACK,true)\nDebug.PreSummon(c,SUMMON_TYPE_LINK)\n"
	         + mz(270000401, 1) + "Debug.AddCard(5318639,1,1,LOCATION_SZONE,0,POS_FACEDOWN_DEFENSE)\n")
	d = proc_case(setup, battle=True)
	expect(not lua_bool(d, card(270000413) + ":IsCanBeEffectTarget()"), "Sparkling can be targeted")
	n0 = len(d.messages)
	play(d, [Phase("bp")], stop="battle")
	opp_chains = [m for m in d.messages[n0:] if m.name == "SELECT_CHAIN" and m.player == 1]
	expect(opp_chains, "no chain window for the opponent in the Battle Phase")
	expect(all(not any(x["code"] == MST for x in m.data["chains"]) for m in opp_chains),
	       "opponent could activate a card during the Battle Phase")
	# in the Main Phase the Set card can be activated (the lock is Battle Phase only)
	d2 = proc_case(setup, hand=[POT])
	n0 = len(d2.messages)
	play(d2, [Act(POT)])
	opp = [m for m in d2.messages[n0:] if m.name == "SELECT_CHAIN" and m.player == 1]
	expect(any(any(x["code"] == MST for x in m.data["chains"]) for m in opp), "opponent could not activate in the Main Phase")
	return d2

@test
def sclash_cross_z_gains_atk_when_cards_are_banished():
	d = proc_case("local c=Debug.AddCard(270000414,0,0,LOCATION_MZONE,0,POS_FACEUP_ATTACK,true)\nDebug.PreSummon(c,SUMMON_TYPE_LINK)\n"
	              + "Debug.AddCard(40640057,1,1,LOCATION_GRAVE,0,POS_FACEUP_ATTACK)\n", hand=[24508238])
	play(d, [Act(24508238), Pick(40640057)])
	expect(40640057 in d.codes(1, "removed"), "D.D. Crow did not banish")
	a = int(lua_val(d, card(270000414) + ":GetAttack()"))
	expect(a == 3300, f"Sclash Cross-Z ATK {a}, expected 3300")
	return d

@test
def true_ashens_king_makes_everything_zombie():
	d = proc_case("local c=Debug.AddCard(270000210,0,0,LOCATION_MZONE,5,POS_FACEUP_ATTACK,true)\nDebug.PreSummon(c,SUMMON_TYPE_LINK)\n"
	              + mz(89631139, 0, player=1), grave=[46986414])
	expect(lua_bool(d, card(89631139, 1) + ":IsRace(RACE_ZOMBIE)"), "opponent monster not a Zombie")
	expect(lua_bool(d, card(46986414, 0, "LOCATION_GRAVE") + ":IsRace(RACE_ZOMBIE)"), "GY monster not a Zombie")
	return d

if __name__ == "__main__":
	res = run_tests(sys.argv[1:] or None)
	w = max(len(n) for n, _, _ in res)
	for name, st, msg in res:
		print(f"{st:5} {name:<{w}} {msg[:600]}")
	print(f"{sum(1 for _, s, _ in res if s == 'PASS')}/{len(res)} passed")
	sys.exit(0 if all(s == "PASS" for _, s, _ in res) else 1)
