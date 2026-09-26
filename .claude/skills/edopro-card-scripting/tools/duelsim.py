#!/usr/bin/env python3
"""Headless duels on ygopro-core, the engine EDOPro embeds.

Loads the libocgcore.so built by `loadcheck.py setup` through ctypes, serves card data from
the .cdb files and scripts from CardScripts and the custom-card folders, decodes every prompt
the engine sends and answers it with a policy (scripted steps, conservative defaults, or a
seeded random explorer). Lua errors raised by the engine are collected, so an effect that
breaks while it resolves shows up as a test failure.

Library for explore.py (random exploration) and scenario.py (scripted tests); see README.md.

Custom cards are read from every folder in EDOPRO_CUSTOM (os.pathsep-separated), the
ZedjaCustomCards folder of CardScripts, and sibling repositories named *customcards* (their
`script/` subfolder included). A folder can hold scripts (c<passcode>.lua) and/or .cdb files.
"""
from __future__ import annotations

import ctypes as C
import os
import random
import sqlite3
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

CORE = Path(os.environ.get("OCGCORE", common.CACHE_DIR / "libocgcore.so"))
SCRIPTS_ROOT = common.SCRIPTS_ROOT


def custom_dirs() -> list[Path]:
	"""Folders that hold custom scripts and/or databases (highest priority first)."""
	out: list[Path] = []
	for item in os.environ.get("EDOPRO_CUSTOM", "").split(os.pathsep):
		if item:
			out.append(Path(item))
	out.append(common.CUSTOM_DIR)
	for d in sorted(common.WORKSPACE.iterdir()):
		if d.is_dir() and "customcards" in d.name.lower() and d.resolve() != common.SCRIPTS_ROOT.resolve():
			out.append(d)
	res = []
	for d in out:
		for x in (d, d / "script"):
			if x.is_dir() and x.resolve() not in [r.resolve() for r in res]:
				res.append(x)
	return res


CUSTOM_DIRS = custom_dirs()
SCRIPT_DIRS = CUSTOM_DIRS + [SCRIPTS_ROOT / f for f in common.SCRIPT_FOLDERS if f != common.CUSTOM_FOLDER]

# ---------------------------------------------------------------- constants
LOC = {"deck": 0x01, "hand": 0x02, "mzone": 0x04, "szone": 0x08, "grave": 0x10, "removed": 0x20,
       "extra": 0x40, "overlay": 0x80, "fzone": 0x100, "pzone": 0x200}
LOC_NAME = {v: k for k, v in LOC.items()}
POS_FACEUP_ATTACK, POS_FACEDOWN_ATTACK, POS_FACEUP_DEFENSE, POS_FACEDOWN_DEFENSE = 1, 2, 4, 8
POS_FACEUP, POS_FACEDOWN = 5, 10
TYPE_MONSTER, TYPE_SPELL, TYPE_TRAP = 0x1, 0x2, 0x4
TYPE_FUSION, TYPE_RITUAL, TYPE_SYNCHRO, TYPE_XYZ, TYPE_LINK = 0x40, 0x80, 0x2000, 0x800000, 0x4000000
TYPE_PENDULUM, TYPE_TOKEN = 0x1000000, 0x4000
TYPE_FIELD, TYPE_CONTINUOUS, TYPE_EQUIP = 0x80000, 0x20000, 0x40000
EXTRA_TYPES = TYPE_FUSION | TYPE_SYNCHRO | TYPE_XYZ | TYPE_LINK
DUEL_MODE_MR5 = 0x800 | 0x2000 | 0x4000 | 0x8000 | 0x20000
DUEL_ATTACK_FIRST_TURN = 0x02
DUEL_PSEUDO_SHUFFLE = 0x10

MSG = dict(RETRY=1, HINT=2, WIN=5, SELECT_BATTLECMD=10, SELECT_IDLECMD=11, SELECT_EFFECTYN=12,
           SELECT_YESNO=13, SELECT_OPTION=14, SELECT_CARD=15, SELECT_CHAIN=16, SELECT_PLACE=18,
           SELECT_POSITION=19, SELECT_TRIBUTE=20, SORT_CHAIN=21, SELECT_COUNTER=22, SELECT_SUM=23,
           SELECT_DISFIELD=24, SORT_CARD=25, SELECT_UNSELECT_CARD=26, NEW_TURN=40, NEW_PHASE=41,
           MOVE=50, SUMMONED=61, SPSUMMONED=63, CHAINING=70, CHAIN_SOLVED=73, CHAIN_NEGATED=75,
           CHAIN_DISABLED=76, DAMAGE=91, RECOVER=92, ROCK_PAPER_SCISSORS=132, ANNOUNCE_RACE=140,
           ANNOUNCE_ATTRIB=141, ANNOUNCE_CARD=142, ANNOUNCE_NUMBER=143)
MSG_NAME = {v: k for k, v in MSG.items()}
PROMPTS = {MSG[k] for k in ("SELECT_BATTLECMD", "SELECT_IDLECMD", "SELECT_EFFECTYN", "SELECT_YESNO",
                            "SELECT_OPTION", "SELECT_CARD", "SELECT_CHAIN", "SELECT_PLACE", "SELECT_POSITION",
                            "SELECT_TRIBUTE", "SORT_CHAIN", "SELECT_COUNTER", "SELECT_SUM", "SELECT_DISFIELD",
                            "SORT_CARD", "SELECT_UNSELECT_CARD", "ROCK_PAPER_SCISSORS", "ANNOUNCE_RACE",
                            "ANNOUNCE_ATTRIB", "ANNOUNCE_CARD", "ANNOUNCE_NUMBER")}

# ---------------------------------------------------------------- ctypes
class CardData(C.Structure):
	_fields_ = [("code", C.c_uint32), ("alias", C.c_uint32), ("setcodes", C.POINTER(C.c_uint16)),
	            ("type", C.c_uint32), ("level", C.c_uint32), ("attribute", C.c_uint32), ("race", C.c_uint64),
	            ("attack", C.c_int32), ("defense", C.c_int32), ("lscale", C.c_uint32), ("rscale", C.c_uint32),
	            ("link_marker", C.c_uint32)]

class Player(C.Structure):
	_fields_ = [("startingLP", C.c_uint32), ("startingDrawCount", C.c_uint32), ("drawCountPerTurn", C.c_uint32)]

DataReader = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.POINTER(CardData))
DataReaderDone = C.CFUNCTYPE(None, C.c_void_p, C.POINTER(CardData))
ScriptReader = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p, C.c_char_p)
LogHandler = C.CFUNCTYPE(None, C.c_void_p, C.c_char_p, C.c_int)

class DuelOptions(C.Structure):
	_fields_ = [("seed", C.c_uint64 * 4), ("flags", C.c_uint64), ("team1", Player), ("team2", Player),
	            ("cardReader", DataReader), ("payload1", C.c_void_p), ("scriptReader", ScriptReader),
	            ("payload2", C.c_void_p), ("logHandler", LogHandler), ("payload3", C.c_void_p),
	            ("cardReaderDone", DataReaderDone), ("payload4", C.c_void_p), ("enableUnsafeLibraries", C.c_uint8)]

class NewCardInfo(C.Structure):
	_fields_ = [("team", C.c_uint8), ("duelist", C.c_uint8), ("code", C.c_uint32), ("con", C.c_uint8),
	            ("loc", C.c_uint32), ("seq", C.c_uint32), ("pos", C.c_uint32)]

if not CORE.exists():
	sys.exit(f"duelsim: {CORE} not found; run `loadcheck.py setup` first (or set OCGCORE)")
lib = C.CDLL(str(CORE))
lib.OCG_CreateDuel.argtypes = [C.POINTER(C.c_void_p), C.POINTER(DuelOptions)]
lib.OCG_DestroyDuel.argtypes = [C.c_void_p]
lib.OCG_DuelNewCard.argtypes = [C.c_void_p, C.POINTER(NewCardInfo)]
lib.OCG_StartDuel.argtypes = [C.c_void_p]
lib.OCG_DuelProcess.argtypes = [C.c_void_p]
lib.OCG_DuelGetMessage.argtypes = [C.c_void_p, C.POINTER(C.c_uint32)]
lib.OCG_DuelGetMessage.restype = C.c_void_p
lib.OCG_DuelSetResponse.argtypes = [C.c_void_p, C.c_void_p, C.c_uint32]
lib.OCG_LoadScript.argtypes = [C.c_void_p, C.c_char_p, C.c_uint32, C.c_char_p]
lib.OCG_DuelQueryCount.argtypes = [C.c_void_p, C.c_uint8, C.c_uint32]

# ---------------------------------------------------------------- card database
class CardDB:
	def __init__(self):
		files = [p for d in CUSTOM_DIRS for p in sorted(d.glob("*.cdb"))]
		files += [p for p in common.cdb_paths() if "rush" not in p.name.lower()]
		seen, self.cons, self.custom = set(), [], set()
		for f in files:
			if f.resolve() in seen:
				continue
			seen.add(f.resolve())
			con = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
			self.cons.append(con)
			if any(f.parent.resolve() == d.resolve() for d in CUSTOM_DIRS):
				self.custom.update(r[0] for r in con.execute("select id from datas"))
		self.cache: dict[int, tuple | None] = {}

	def row(self, code: int):
		if code in self.cache:
			return self.cache[code]
		r = None
		for con in self.cons:
			r = con.execute("select d.id,d.alias,d.setcode,d.type,d.atk,d.def,d.level,d.race,d.attribute,t.name "
			                "from datas d left join texts t on t.id=d.id where d.id=?", (code,)).fetchone()
			if r:
				break
		self.cache[code] = r
		return r

	def name(self, code: int) -> str:
		r = self.row(code)
		return r[9] if r and r[9] else str(code)

	def type(self, code: int) -> int:
		r = self.row(code)
		return r[3] if r else 0

	def setcodes(self, code: int) -> list[int]:
		r = self.row(code)
		if not r:
			return []
		sc = r[2] & 0xFFFFFFFFFFFFFFFF
		return [(sc >> (16 * i)) & 0xFFFF for i in range(4) if (sc >> (16 * i)) & 0xFFFF]

	def codes_with_setcode(self, setcode: int, cons=None) -> list[int]:
		out = []
		for con in (cons or self.cons):
			for (cid, sc) in con.execute("select id,setcode from datas"):
				sc &= 0xFFFFFFFFFFFFFFFF
				for i in range(4):
					s = (sc >> (16 * i)) & 0xFFFF
					if s and (s & 0xFFF) == (setcode & 0xFFF) and (s & 0xF000 & setcode) == (setcode & 0xF000):
						out.append(cid)
						break
		return sorted(set(out))

DB = CardDB()

def find_script(name: str) -> Path | None:
	"""Card scripts from the custom folders first, then CardScripts; libraries from the root."""
	if name.startswith("c") and name.endswith(".lua") and name[1:-4].isdigit():
		for d in SCRIPT_DIRS:
			p = d / name
			if p.exists():
				return p
		return None
	for d in (SCRIPTS_ROOT, SCRIPTS_ROOT / "unofficial"):
		p = d / name
		if p.exists():
			return p
	return None

# ---------------------------------------------------------------- message decoding
class Reader:
	def __init__(self, b: bytes):
		self.b, self.i = b, 0
	def u8(self): v = self.b[self.i]; self.i += 1; return v
	def i8(self): v = struct.unpack_from("<b", self.b, self.i)[0]; self.i += 1; return v
	def u16(self): v = struct.unpack_from("<H", self.b, self.i)[0]; self.i += 2; return v
	def u32(self): v = struct.unpack_from("<I", self.b, self.i)[0]; self.i += 4; return v
	def i32(self): v = struct.unpack_from("<i", self.b, self.i)[0]; self.i += 4; return v
	def u64(self): v = struct.unpack_from("<Q", self.b, self.i)[0]; self.i += 8; return v
	def loc(self): return dict(con=self.u8(), loc=self.u8(), seq=self.u32(), pos=self.u32())

@dataclass
class Msg:
	type: int
	raw: bytes
	data: dict = field(default_factory=dict)
	@property
	def name(self): return MSG_NAME.get(self.type, str(self.type))
	@property
	def player(self): return self.data.get("player")

def decode(mtype: int, raw: bytes) -> Msg:
	m = Msg(mtype, raw)
	r = Reader(raw)
	d = m.data
	try:
		if mtype == MSG["SELECT_IDLECMD"]:
			d["player"] = r.u8()
			def cl(seq8=False):
				n = r.u32(); out = []
				for _ in range(n):
					out.append(dict(code=r.u32(), con=r.u8(), loc=r.u8(), seq=(r.u8() if seq8 else r.u32())))
				return out
			d["summon"] = cl(); d["spsummon"] = cl(); d["repos"] = cl(True); d["mset"] = cl(); d["sset"] = cl()
			n = r.u32(); d["activate"] = [dict(code=r.u32(), con=r.u8(), loc=r.u8(), seq=r.u32(), desc=r.u64(), mode=r.u8()) for _ in range(n)]
			d["bp"], d["ep"], d["shuffle"] = r.u8(), r.u8(), r.u8()
		elif mtype == MSG["SELECT_BATTLECMD"]:
			d["player"] = r.u8()
			n = r.u32(); d["activate"] = [dict(code=r.u32(), con=r.u8(), loc=r.u8(), seq=r.u32(), desc=r.u64(), mode=r.u8()) for _ in range(n)]
			n = r.u32(); d["attack"] = [dict(code=r.u32(), con=r.u8(), loc=r.u8(), seq=r.u8(), direct=r.u8()) for _ in range(n)]
			d["m2"], d["ep"] = r.u8(), r.u8()
		elif mtype == MSG["SELECT_EFFECTYN"]:
			d["player"] = r.u8(); d["code"] = r.u32(); d.update(r.loc()); d["desc"] = r.u64()
		elif mtype == MSG["SELECT_YESNO"]:
			d["player"] = r.u8(); d["desc"] = r.u64()
		elif mtype == MSG["SELECT_OPTION"]:
			d["player"] = r.u8(); n = r.u8(); d["options"] = [r.u64() for _ in range(n)]
		elif mtype == MSG["SELECT_CARD"]:
			d["player"] = r.u8(); d["cancelable"] = r.u8(); d["min"] = r.u32(); d["max"] = r.u32()
			n = r.u32(); d["cards"] = [dict(code=r.u32(), **r.loc()) for _ in range(n)]
		elif mtype == MSG["SELECT_CHAIN"]:
			d["player"] = r.u8(); d["spe"] = r.u8(); d["forced"] = r.u8(); d["hint0"] = r.u32(); d["hint1"] = r.u32()
			n = r.u32(); d["chains"] = [dict(code=r.u32(), **r.loc(), desc=r.u64(), mode=r.u8()) for _ in range(n)]
		elif mtype in (MSG["SELECT_PLACE"], MSG["SELECT_DISFIELD"]):
			d["player"] = r.u8(); d["count"] = r.u8(); d["flag"] = r.u32()
		elif mtype == MSG["SELECT_POSITION"]:
			d["player"] = r.u8(); d["code"] = r.u32(); d["positions"] = r.u8()
		elif mtype == MSG["SELECT_TRIBUTE"]:
			d["player"] = r.u8(); d["cancelable"] = r.u8(); d["min"] = r.u32(); d["max"] = r.u32()
			n = r.u32(); d["cards"] = [dict(code=r.u32(), con=r.u8(), loc=r.u8(), seq=r.u32(), release=r.u8()) for _ in range(n)]
		elif mtype == MSG["SELECT_COUNTER"]:
			d["player"] = r.u8(); d["ctype"] = r.u16(); d["count"] = r.u16()
			n = r.u32(); d["cards"] = [dict(code=r.u32(), con=r.u8(), loc=r.u8(), seq=r.u8(), counters=r.u16()) for _ in range(n)]
		elif mtype == MSG["SELECT_SUM"]:
			d["player"] = r.u8(); d["mode"] = r.u8(); d["acc"] = r.u32(); d["min"] = r.u32(); d["max"] = r.u32()
			n = r.u32(); d["must"] = [dict(code=r.u32(), **r.loc(), param=r.u32()) for _ in range(n)]
			n = r.u32(); d["cards"] = [dict(code=r.u32(), **r.loc(), param=r.u32()) for _ in range(n)]
		elif mtype in (MSG["SORT_CARD"], MSG["SORT_CHAIN"]):
			d["player"] = r.u8(); n = r.u32(); d["cards"] = [dict(code=r.u32(), con=r.u8(), loc=r.u32(), seq=r.u32()) for _ in range(n)]
		elif mtype == MSG["SELECT_UNSELECT_CARD"]:
			d["player"] = r.u8(); d["finishable"] = r.u8(); d["cancelable"] = r.u8(); d["min"] = r.u32(); d["max"] = r.u32()
			n = r.u32(); d["select"] = [dict(code=r.u32(), **r.loc()) for _ in range(n)]
			n = r.u32(); d["unselect"] = [dict(code=r.u32(), **r.loc()) for _ in range(n)]
		elif mtype == MSG["ANNOUNCE_RACE"]:
			d["player"] = r.u8(); d["count"] = r.u8(); d["available"] = r.u64()
		elif mtype == MSG["ANNOUNCE_ATTRIB"]:
			d["player"] = r.u8(); d["count"] = r.u8(); d["available"] = r.u32()
		elif mtype in (MSG["ANNOUNCE_CARD"], MSG["ANNOUNCE_NUMBER"]):
			d["player"] = r.u8(); n = r.u8(); d["options"] = [r.u64() for _ in range(n)]
		elif mtype == MSG["ROCK_PAPER_SCISSORS"]:
			d["player"] = r.u8()
		elif mtype == MSG["HINT"]:
			d["htype"] = r.u8(); d["player"] = r.u8(); d["hdata"] = r.u64()
		elif mtype == MSG["WIN"]:
			d["player"] = r.u8(); d["reason"] = r.u8()
		elif mtype == MSG["NEW_TURN"]:
			d["player"] = r.u8()
		elif mtype == MSG["NEW_PHASE"]:
			d["phase"] = r.u16()
		elif mtype == MSG["CHAINING"]:
			d["code"] = r.u32(); d.update(r.loc()); d["tcon"] = r.u8(); d["tloc"] = r.u8(); d["tseq"] = r.u32()
			d["desc"] = r.u64(); d["count"] = r.u32()
		elif mtype == MSG["MOVE"]:
			d["code"] = r.u32(); d["prev"] = r.loc(); d["cur"] = r.loc(); d["reason"] = r.u32()
	except (IndexError, struct.error):
		d["_decode_error"] = True
	return m

# ---------------------------------------------------------------- response encoding
def i32(v): return struct.pack("<i", v)
def resp_cards(indices): return struct.pack("<iI", 0, len(indices)) + b"".join(struct.pack("<I", i) for i in indices)
def resp_cancel(): return i32(-1)
def resp_idle(t, s=0): return i32((s << 16) | t)

def desc_code(desc): return desc >> 20
def desc_index(desc): return desc & 0xFFFFF

def free_places(flag: int, player: int):
	"""Zones not blocked by `flag` (bits set = unavailable). Returns (player, location, seq)."""
	out = []
	for side in (0, 1):
		p = player if side == 0 else 1 - player
		base = 16 * side
		for seq in range(7):
			if not (flag >> (base + seq)) & 1:
				out.append((p, 0x04, seq))
		for seq in range(8):
			if not (flag >> (base + 8 + seq)) & 1:
				out.append((p, 0x08, seq))
	return out

def sum_solutions(d, limit=64):
	"""Index lists over d['cards'] whose sum parameters satisfy the SELECT_SUM request."""
	acc, must, cards = d["acc"], d["must"], d["cards"]
	exact = d["mode"] == 0
	def opts(p):
		o1, o2 = p & 0xFFFF, p >> 16
		return [o1] + ([o2] if o2 else [])
	base = [opts(c["param"]) for c in must]
	sols = []
	n = len(cards)
	def ok(sel):
		params = base + [opts(cards[i]["param"]) for i in sel]
		if exact:
			tot = len(sel)
			if tot < d["min"] or (d["max"] and tot > d["max"]):
				return False
			def rec(k, rem):
				if k == len(params):
					return rem == 0
				return any(rem - v >= 0 and rec(k + 1, rem - v) for v in params[k])
			return rec(0, acc)
		mins = [min(p) for p in params]; maxs = [max(p) for p in params]
		if sum(maxs) < acc:
			return False
		return not (sum(mins) - min(mins) >= acc) if mins else False
	from itertools import combinations
	for k in range(1, min(n, 6) + 1):
		for sel in combinations(range(n), k):
			if ok(sel):
				sols.append(list(sel))
				if len(sols) >= limit:
					return sols
	return sols

# ---------------------------------------------------------------- policies
class Policy:
	"""Base policy: deterministic, conservative defaults."""
	yes = True
	def respond(self, duel: "Duel", m: Msg) -> bytes:
		return getattr(self, "on_" + m.name.lower())(duel, m)

	def on_select_idlecmd(self, duel, m):
		d = m.data
		return resp_idle(7) if d["ep"] else resp_idle(6)
	def on_select_battlecmd(self, duel, m):
		d = m.data
		if d["ep"]:
			return resp_idle(3)
		if d["m2"]:
			return resp_idle(2)
		if d["attack"]:
			return resp_idle(1, 0)
		return resp_idle(0, 0)
	def on_select_effectyn(self, duel, m): return i32(1 if self.yes else 0)
	def on_select_yesno(self, duel, m): return i32(1 if self.yes else 0)
	def on_select_option(self, duel, m): return i32(0)
	def on_select_card(self, duel, m):
		d = m.data
		return resp_cards(list(range(max(d["min"], 1) if d["max"] else 0)))
	def on_select_chain(self, duel, m):
		return i32(0) if m.data["forced"] else i32(-1)
	def on_select_place(self, duel, m):
		d = m.data
		places = free_places(d["flag"], d["player"])
		out = b""
		for i in range(d["count"]):
			p = places[i % len(places)]
			out += bytes(p)
		return out
	on_select_disfield = on_select_place
	def on_select_position(self, duel, m):
		pos = m.data["positions"]
		for p in (1, 4, 2, 8):
			if pos & p:
				return i32(p)
		return i32(1)
	def on_select_tribute(self, duel, m):
		d = m.data
		idx, tot = [], 0
		for i, c in enumerate(d["cards"]):
			if tot >= d["min"]:
				break
			idx.append(i); tot += c["release"]
		return resp_cards(idx)
	def on_select_counter(self, duel, m):
		d = m.data
		need, out = d["count"], b""
		for c in d["cards"]:
			take = min(need, c["counters"]); need -= take
			out += struct.pack("<h", take)
		return out
	def on_select_sum(self, duel, m):
		sols = sum_solutions(m.data)
		return resp_cards(sols[0] if sols else [0])
	def on_sort_card(self, duel, m): return struct.pack("<b", -1)
	on_sort_chain = on_sort_card
	def on_select_unselect_card(self, duel, m):
		d = m.data
		if d["finishable"]:
			return i32(-1)
		if d["select"]:
			return struct.pack("<ii", 1, 0)
		if d["cancelable"]:
			return i32(-1)
		return struct.pack("<ii", 1, 0)
	def on_rock_paper_scissors(self, duel, m): return i32(1)
	def on_announce_race(self, duel, m):
		d = m.data; v = 0; bits = [1 << i for i in range(64) if d["available"] >> i & 1]
		for b in bits[:d["count"]]: v |= b
		return struct.pack("<Q", v)
	def on_announce_attrib(self, duel, m):
		d = m.data; v = 0; bits = [1 << i for i in range(32) if d["available"] >> i & 1]
		for b in bits[:d["count"]]: v |= b
		return struct.pack("<I", v)
	def on_announce_number(self, duel, m): return i32(0)
	def on_announce_card(self, duel, m):
		# declare a common card that is usually valid: try a few codes
		for code in duel.announce_candidates:
			return i32(code)
		return i32(89631139)

class RandomPolicy(Policy):
	"""Seeded explorer: prefers doing things (activations, summons) over passing."""
	def __init__(self, seed: int, act_bias: float = 0.8, players=(0, 1), passive_players=()):
		self.rng = random.Random(seed)
		self.act_bias = act_bias
		self.passive = set(passive_players)
		self.idle_count = 0

	def on_select_idlecmd(self, duel, m):
		d = m.data
		self.idle_count += 1
		if m.player in self.passive:
			return super().on_select_idlecmd(duel, m)
		choices = []
		for t, key in ((5, "activate"), (1, "spsummon"), (0, "summon"), (4, "sset"), (3, "mset")):
			for s in range(len(d[key])):
				w = {5: 6, 1: 4, 0: 3, 4: 1, 3: 1}[t]
				choices += [(t, s)] * w
		if choices and self.rng.random() < self.act_bias:
			t, s = self.rng.choice(choices)
			return resp_idle(t, s)
		if d["bp"] and self.rng.random() < 0.5:
			return resp_idle(6)
		return resp_idle(7) if d["ep"] else resp_idle(6)

	def on_select_battlecmd(self, duel, m):
		d = m.data
		if m.player not in self.passive:
			if d["activate"] and self.rng.random() < 0.5:
				return resp_idle(0, self.rng.randrange(len(d["activate"])))
			if d["attack"] and self.rng.random() < 0.7:
				return resp_idle(1, self.rng.randrange(len(d["attack"])))
		if d["m2"]:
			return resp_idle(2)
		if d["ep"]:
			return resp_idle(3)
		return Policy.on_select_battlecmd(self, duel, m)

	def on_select_chain(self, duel, m):
		d = m.data
		if d["chains"] and (d["forced"] or (m.player not in self.passive and self.rng.random() < 0.7)):
			return i32(self.rng.randrange(len(d["chains"])))
		return i32(-1)

	def on_select_effectyn(self, duel, m): return i32(1 if self.rng.random() < 0.8 else 0)
	def on_select_yesno(self, duel, m): return i32(1 if self.rng.random() < 0.7 else 0)
	def on_select_option(self, duel, m): return i32(self.rng.randrange(len(m.data["options"])))
	def on_select_card(self, duel, m):
		d = m.data
		n = len(d["cards"])
		if d["cancelable"] and d["min"] > 0 and self.rng.random() < 0.05:
			return resp_cancel()
		lo = max(d["min"], 0); hi = max(lo, min(d["max"], n))
		k = self.rng.randint(max(lo, 1) if hi else 0, hi) if hi else 0
		return resp_cards(sorted(self.rng.sample(range(n), k)))
	def on_select_tribute(self, duel, m):
		d = m.data
		order = list(range(len(d["cards"]))); self.rng.shuffle(order)
		idx, tot = [], 0
		for i in order:
			if tot >= d["min"]:
				break
			idx.append(i); tot += d["cards"][i]["release"]
		return resp_cards(sorted(idx))
	def on_select_sum(self, duel, m):
		sols = sum_solutions(m.data)
		return resp_cards(self.rng.choice(sols) if sols else [0])
	def on_select_place(self, duel, m):
		d = m.data
		places = free_places(d["flag"], d["player"])
		self.rng.shuffle(places)
		own = [p for p in places if p[0] == d["player"]] or places
		out = b""
		for i in range(d["count"]):
			out += bytes(own[i % len(own)])
		return out
	on_select_disfield = on_select_place
	def on_select_position(self, duel, m):
		opts = [p for p in (1, 2, 4, 8) if m.data["positions"] & p]
		return i32(self.rng.choice(opts) if opts else 1)
	def on_announce_number(self, duel, m): return i32(self.rng.randrange(len(m.data["options"])))
	def on_announce_attrib(self, duel, m):
		d = m.data; bits = [1 << i for i in range(32) if d["available"] >> i & 1]
		self.rng.shuffle(bits); v = 0
		for b in bits[:d["count"]]: v |= b
		return struct.pack("<I", v)
	def on_announce_race(self, duel, m):
		d = m.data; bits = [1 << i for i in range(64) if d["available"] >> i & 1]
		self.rng.shuffle(bits); v = 0
		for b in bits[:d["count"]]: v |= b
		return struct.pack("<Q", v)
	def on_select_unselect_card(self, duel, m):
		d = m.data
		if d["finishable"] and self.rng.random() < 0.5:
			return i32(-1)
		if d["select"]:
			return struct.pack("<ii", 1, self.rng.randrange(len(d["select"])))
		if d["finishable"] or d["cancelable"]:
			return i32(-1)
		return struct.pack("<ii", 1, 0)

# ---------------------------------------------------------------- duel
class DuelError(Exception):
	pass

class Duel:
	def __init__(self, seed=1, flags=DUEL_MODE_MR5 | DUEL_PSEUDO_SHUFFLE, lp=8000):
		self.errors: list[str] = []      # Lua/engine errors
		self.script_log: list[str] = []  # Debug.Message output
		self.messages: list[Msg] = []
		self.trace: list[tuple] = []     # (prompt name, player, response hex)
		self.retries = 0
		self.retry_log: list[tuple] = []
		self.missing_scripts: set[str] = set()
		self.ended = False
		self.winner = None
		self.announce_candidates = [89631139]
		self._setcode_bufs = {}
		self._cb_card = DataReader(self._read_card)
		self._cb_done = DataReaderDone(lambda p, d: None)
		self._cb_script = ScriptReader(self._read_script)
		self._cb_log = LogHandler(self._log)
		opts = DuelOptions()
		for i in range(4):
			opts.seed[i] = (seed * 0x9E3779B97F4A7C15 + i * 0x12345) & 0xFFFFFFFFFFFFFFFF or 1
		opts.flags = flags
		opts.team1 = Player(lp, 0, 1)
		opts.team2 = Player(lp, 0, 1)
		opts.cardReader = self._cb_card
		opts.scriptReader = self._cb_script
		opts.logHandler = self._cb_log
		opts.cardReaderDone = self._cb_done
		self.ptr = C.c_void_p()
		st = lib.OCG_CreateDuel(C.byref(self.ptr), C.byref(opts))
		if st != 0:
			raise DuelError(f"OCG_CreateDuel failed: {st}")
		for s in ("constant.lua", "utility.lua"):
			if not self._load_file(s):
				raise DuelError("cannot load " + s)

	# callbacks -----------------------------------------------------------
	def _read_card(self, payload, code, out):
		r = DB.row(code)
		cd = out.contents
		cd.code = code
		if not r:
			return
		_, alias, setcode, typ, atk, df, level, race, attr, _ = r
		cd.alias = alias
		sc = setcode & 0xFFFFFFFFFFFFFFFF
		codes = [(sc >> (16 * i)) & 0xFFFF for i in range(4)]
		codes = [c for c in codes if c] + [0]
		buf = (C.c_uint16 * len(codes))(*codes)
		self._setcode_bufs[code] = buf
		cd.setcodes = C.cast(buf, C.POINTER(C.c_uint16))
		cd.type = typ
		cd.level = level & 0xFF
		cd.lscale = (level >> 24) & 0xFF
		cd.rscale = (level >> 16) & 0xFF
		cd.attribute = attr
		cd.race = race
		cd.attack = atk
		if typ & TYPE_LINK:
			cd.link_marker = df; cd.defense = 0
		else:
			cd.defense = df; cd.link_marker = 0

	def _load_file(self, name: str) -> bool:
		p = find_script(name)
		if not p:
			return False
		data = p.read_bytes()
		return lib.OCG_LoadScript(self.ptr, data, len(data), name.encode()) > 0

	def _read_script(self, payload, duel, name):
		n = name.decode()
		ok = self._load_file(os.path.basename(n))
		if not ok:
			self.missing_scripts.add(n)
		return 1 if ok else 0

	def _log(self, payload, s, t):
		msg = s.decode(errors="replace")
		if t == 1:
			self.script_log.append(msg)
		else:
			self.errors.append(msg)

	# setup ---------------------------------------------------------------
	def add(self, code, player=0, loc="deck", seq=0, pos=None, owner=None):
		l = LOC[loc] if isinstance(loc, str) else loc
		if pos is None:
			if l in (LOC["mzone"],):
				pos = POS_FACEUP_ATTACK
			elif l in (LOC["szone"], LOC["fzone"], LOC["pzone"]):
				pos = POS_FACEUP_ATTACK
			elif l == LOC["removed"] or l == LOC["grave"]:
				pos = POS_FACEUP_ATTACK
			else:
				pos = POS_FACEDOWN_DEFENSE
		if l == LOC["fzone"]:
			l, seq = LOC["szone"], 5
		elif l == LOC["pzone"]:
			l = LOC["szone"]; seq = 0 if seq == 0 else 4
		info = NewCardInfo(owner if owner is not None else player, 0, code, player, l, seq, pos)
		lib.OCG_DuelNewCard(self.ptr, C.byref(info))

	def start(self):
		lib.OCG_StartDuel(self.ptr)

	def lua(self, code: str, name="probe.lua") -> list[str]:
		"""Run Lua inside the duel; returns the Debug.Message lines it produced."""
		before = len(self.script_log)
		data = code.encode()
		lib.OCG_LoadScript(self.ptr, data, len(data), name.encode())
		return self.script_log[before:]

	def state(self) -> dict:
		"""Field snapshot via a Lua probe: {(player, loc): [(code, pos, atk, faceup), ...]}."""
		out = self.lua("""
local locs={0x01,0x02,0x04,0x08,0x10,0x20,0x40}
for p=0,1 do for _,l in ipairs(locs) do
  local g=Duel.GetFieldGroup(p,l,0)
  local parts={}
  for c in g:Iter() do
    local atk=c:IsLocation(LOCATION_MZONE) and c:GetAttack() or -1
    parts[#parts+1]=c:GetCode()..':'..c:GetPosition()..':'..atk..':'..c:GetSequence()..':'..c:GetOverlayCount()
  end
  Debug.Message('ST|'..p..'|'..l..'|'..table.concat(parts,','))
end end
Debug.Message('LP|'..Duel.GetLP(0)..'|'..Duel.GetLP(1))
""", "state.lua")
		st = {}
		for line in out:
			parts = line.split("|")
			if parts[0] == "ST":
				p, l = int(parts[1]), int(parts[2])
				cards = []
				if parts[3]:
					for item in parts[3].split(","):
						code, pos, atk, seq, ov = item.split(":")
						cards.append(dict(code=int(code), pos=int(pos), atk=int(atk), seq=int(seq), overlay=int(ov)))
				st[(p, LOC_NAME[l])] = cards
			elif parts[0] == "LP":
				st["lp"] = (int(parts[1]), int(parts[2]))
		return st

	def codes(self, player, loc) -> list[int]:
		return [c["code"] for c in self.state().get((player, loc), [])]

	# processing ----------------------------------------------------------
	def _fetch(self) -> list[Msg]:
		n = C.c_uint32()
		ptr = lib.OCG_DuelGetMessage(self.ptr, C.byref(n))
		raw = C.string_at(ptr, n.value) if n.value else b""
		out, i = [], 0
		while i + 4 <= len(raw):
			ln = struct.unpack_from("<I", raw, i)[0]; i += 4
			body = raw[i:i + ln]; i += ln
			if body:
				out.append(decode(body[0], body[1:]))
		return out

	def step(self) -> Msg | None:
		"""Process until a prompt (returned) or the end of the duel (None)."""
		for _ in range(10000):
			st = lib.OCG_DuelProcess(self.ptr)
			msgs = self._fetch()
			self.messages.extend(msgs)
			prompt = None
			for m in msgs:
				if m.type == MSG["RETRY"]:
					self.retries += 1
				if m.type == MSG["WIN"]:
					self.ended = True; self.winner = m.data.get("player")
				if m.type in PROMPTS:
					prompt = m
			if st == 0:
				self.ended = True
				return None
			if st == 1:
				if prompt is None:
					if any(m.type == MSG["RETRY"] for m in msgs) and getattr(self, "_last_prompt", None):
						self._retrying = True
						return self._last_prompt
					raise DuelError("awaiting without prompt")
				self._retrying = False
				self._last_prompt = prompt
				return prompt
		raise DuelError("engine did not reach a prompt (possible loop)")

	def respond(self, data: bytes):
		lib.OCG_DuelSetResponse(self.ptr, data, len(data))

	def run(self, policy: Policy, max_prompts=500, until=None) -> int:
		"""Drive the duel with `policy`. `until(duel, prompt)` can stop early (returns True)."""
		n = 0
		last_retry_prompt = None
		while n < max_prompts:
			m = self.step()
			if m is None:
				return n
			if until and until(self, m):
				self.pending = m
				return n
			if self.retries and last_retry_prompt is not None and self.retries > 50:
				raise DuelError("too many invalid responses")
			if getattr(self, "_retrying", False):
				self.retry_log.append((m.name, m.player, self.trace[-1][2] if self.trace else ""))
				resp = Policy().respond(self, m)
			else:
				resp = policy.respond(self, m)
			self.trace.append((m.name, m.player, resp.hex()))
			last_retry_prompt = m
			self.respond(resp)
			n += 1
		return n

	def close(self):
		if self.ptr:
			lib.OCG_DestroyDuel(self.ptr)
			self.ptr = None
	def __del__(self):
		try:
			self.close()
		except Exception:
			pass
