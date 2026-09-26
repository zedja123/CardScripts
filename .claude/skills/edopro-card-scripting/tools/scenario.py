"""Scripted scenario tests on ygopro-core (framework; tests live in scenarios_*.py).

A test builds a board, then plays exact moves with `Scripted`: each step answers one kind of
prompt (activate an effect, pick cards, answer yes/no ...). Prompts that no step covers get a
conservative default (pass, first legal choice, "no" to optional prompts). Assertions then
inspect the field through `Duel.state()` / `Duel.codes()` or a Lua probe.
"""
from __future__ import annotations

import struct
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duelcheck as checks  # noqa: E402
from duelsim import DB, LOC, Duel, Policy, i32, resp_cards, resp_idle  # noqa: E402

class TestFailure(AssertionError):
	pass

def desc_of(code, idx):
	return (code << 20) | idx

class Step:
	kinds: tuple = ()
	def apply(self, duel, m):  # -> bytes | None (None: this step does not handle that prompt)
		raise NotImplementedError
	def __repr__(self):
		return self.__class__.__name__ + str(self.__dict__)

class Act(Step):
	"""Activate the effect of `code` (optionally with string index `idx`) from an idle, battle or chain prompt."""
	def __init__(self, code, idx=None, player=0, loc=None):
		self.code, self.idx, self.player, self.loc = code, idx, player, loc
	def _match(self, x):
		if x["code"] != self.code and (x["desc"] >> 20) != self.code:
			return False
		if self.idx is not None and x["desc"] != desc_of(self.code, self.idx):
			return False
		if self.loc is not None and x["loc"] != LOC[self.loc]:
			return False
		return True
	def apply(self, duel, m):
		if m.player != self.player:
			return None
		d = m.data
		if m.name == "SELECT_IDLECMD":
			for s, x in enumerate(d["activate"]):
				if self._match(x):
					return resp_idle(5, s)
			raise TestFailure(f"cannot activate {self.code}/{self.idx}: available {[(x['code'], x['desc'] & 0xfffff) for x in d['activate']]}")
		if m.name == "SELECT_BATTLECMD":
			for s, x in enumerate(d["activate"]):
				if self._match(x):
					return resp_idle(0, s)
			raise TestFailure(f"cannot activate {self.code}/{self.idx} in battle: {[(x['code'], x['desc'] & 0xfffff) for x in d['activate']]}")
		if m.name == "SELECT_CHAIN":
			for s, x in enumerate(d["chains"]):
				if self._match(x):
					return i32(s)
			return None  # maybe a later chain window
		if m.name == "SELECT_EFFECTYN" and d["code"] == self.code:
			return i32(1)
		return None

class Summon(Step):
	def __init__(self, code, kind="spsummon", player=0):
		self.code, self.kind, self.player = code, kind, player
	def apply(self, duel, m):
		if m.name != "SELECT_IDLECMD" or m.player != self.player:
			return None
		t = {"summon": 0, "spsummon": 1, "mset": 3, "sset": 4}[self.kind]
		for s, x in enumerate(m.data[self.kind]):
			if x["code"] == self.code:
				return resp_idle(t, s)
		raise TestFailure(f"cannot {self.kind} {self.code}: available {[x['code'] for x in m.data[self.kind]]}")

class Pick(Step):
	"""Choose these cards (codes, optionally (code, location)) in a card selection."""
	def __init__(self, *cards, player=0):
		self.cards, self.player = cards, player
	def _index(self, lst):
		out, used = [], set()
		for want in self.cards:
			code, loc = (want if isinstance(want, tuple) else (want, None))
			for i, x in enumerate(lst):
				if i in used or x["code"] != code:
					continue
				if loc is not None and x["loc"] != LOC[loc]:
					continue
				out.append(i); used.add(i); break
			else:
				raise TestFailure(f"card {want} not selectable: {[(x['code'], x['loc']) for x in lst]}")
		return out
	def apply(self, duel, m):
		if m.player != self.player:
			return None
		if m.name in ("SELECT_CARD", "SELECT_TRIBUTE"):
			return resp_cards(self._index(m.data["cards"]))
		if m.name == "SELECT_SUM":
			return resp_cards(self._index(m.data["cards"]))
		if m.name == "SELECT_UNSELECT_CARD":
			# pick one card per prompt; keep the step until all are picked
			idx = self._index(m.data["select"][:] if m.data["select"] else m.data["unselect"])
			self.cards = self.cards[1:]
			r = struct.pack("<ii", 1, idx[0])
			if self.cards:
				self.keep = True
			return r
		return None

class Answer(Step):
	"""Yes/no to a SELECT_YESNO / SELECT_EFFECTYN prompt (optionally only for a given description)."""
	def __init__(self, yes=True, desc=None, player=0):
		self.yes, self.desc, self.player = yes, desc, player
	def apply(self, duel, m):
		if m.player != self.player or m.name not in ("SELECT_YESNO", "SELECT_EFFECTYN"):
			return None
		if self.desc is not None and m.data["desc"] != self.desc:
			return None
		return i32(1 if self.yes else 0)

class Option(Step):
	def __init__(self, desc=None, index=None, player=0):
		self.desc, self.index, self.player = desc, index, player
	def apply(self, duel, m):
		if m.player != self.player or m.name != "SELECT_OPTION":
			return None
		if self.index is not None:
			return i32(self.index)
		opts = m.data["options"]
		if self.desc in opts:
			return i32(opts.index(self.desc))
		raise TestFailure(f"option {self.desc} not offered: {opts}")

class Finish(Step):
	"""End a select/unselect prompt (when finishable)."""
	def __init__(self, player=0):
		self.player = player
	def apply(self, duel, m):
		if m.player == self.player and m.name == "SELECT_UNSELECT_CARD":
			return i32(-1)
		return None

class Phase(Step):
	"""Leave the current phase: 'bp' (to Battle Phase), 'm2', 'ep'."""
	def __init__(self, to, player=0):
		self.to, self.player = to, player
	def apply(self, duel, m):
		if m.player != self.player:
			return None
		if m.name == "SELECT_IDLECMD":
			if self.to == "bp" and not m.data["bp"]:
				raise TestFailure("Battle Phase not available")
			return resp_idle({"bp": 6, "ep": 7}[self.to if self.to != "m2" else "ep"])
		if m.name == "SELECT_BATTLECMD":
			return resp_idle({"m2": 2, "ep": 3}.get(self.to, 3))
		return None

class Attack(Step):
	def __init__(self, code, player=0):
		self.code, self.player = code, player
	def apply(self, duel, m):
		if m.player != self.player or m.name != "SELECT_BATTLECMD":
			return None
		for s, x in enumerate(m.data["attack"]):
			if x["code"] == self.code:
				return resp_idle(1, s)
		raise TestFailure(f"{self.code} cannot attack")

class Scripted(Policy):
	yes = False
	def __init__(self, steps):
		self.steps = list(steps)
	def respond(self, duel, m):
		if self.steps:
			st = self.steps[0]
			r = st.apply(duel, m)
			if r is not None:
				if not getattr(st, "keep", False):
					self.steps.pop(0)
				else:
					st.keep = False
				return r
		return super().respond(duel, m)
	def on_select_idlecmd(self, duel, m):
		if self.steps:
			raise TestFailure(f"idle prompt reached with pending steps {self.steps[:2]}")
		return super().on_select_idlecmd(duel, m)

def play(duel: Duel, steps, stop="idle", player=0, max_prompts=300):
	"""Play `steps`; stop at the next idle prompt of `player` once every step is used."""
	pol = Scripted(steps)
	def until(du, m):
		if pol.steps:
			return False
		if stop == "idle":
			return m.name == "SELECT_IDLECMD" and m.player == player
		if stop == "battle":
			return m.name == "SELECT_BATTLECMD" and m.player == player
		return False
	# answer the pending prompt first (if the previous play stopped on one)
	pending = getattr(duel, "pending", None)
	if pending is not None:
		duel.pending = None
		if until(duel, pending):
			duel.pending = pending
			return pending
		duel.respond(pol.respond(duel, pending))
	duel.run(pol, max_prompts=max_prompts, until=until)
	if pol.steps:
		raise TestFailure(f"steps not used: {pol.steps}")
	return getattr(duel, "pending", None)

def activatable(duel: Duel, player=0):
	"""(code, string index) list at the pending idle prompt."""
	m = duel.pending
	assert m is not None and m.name == "SELECT_IDLECMD", m and m.name
	return [(x["code"], x["desc"] & 0xFFFFF if (x["desc"] >> 20) == x["code"] else x["desc"]) for x in m.data["activate"]]

def new_duel(seed=1, observer=True, first_turn_battle=False):
	from duelsim import DUEL_MODE_MR5, DUEL_PSEUDO_SHUFFLE, DUEL_ATTACK_FIRST_TURN
	flags = DUEL_MODE_MR5 | DUEL_PSEUDO_SHUFFLE | (DUEL_ATTACK_FIRST_TURN if first_turn_battle else 0)
	d = Duel(seed=seed, flags=flags)
	if observer:
		d.lua(checks.OBSERVER, "observer.lua")
	return d

def begin(d: Duel):
	"""Start and stop at the first idle prompt of player 0."""
	d.start()
	d.pending = None
	d.run(Scripted([]), max_prompts=50, until=lambda du, m: m.name == "SELECT_IDLECMD" and m.player == 0)
	return d

def expect(cond, msg):
	if not cond:
		raise TestFailure(msg)

def filler(d, player, n=10, code=89631139):
	for _ in range(n):
		d.add(code, player, "deck")

# ---------------------------------------------------------------- probes
def lua_bool(d, expr):
	out = d.lua(f"Debug.Message('R|'..tostring({expr}))")
	vals = [x[2:] for x in out if x.startswith("R|")]
	if not vals:
		raise TestFailure(f"probe failed: {expr} -> {d.errors[-1:] if d.errors else out}")
	return vals[-1] == "true"

def lua_val(d, expr):
	out = d.lua(f"Debug.Message('R|'..tostring({expr}))")
	vals = [x[2:] for x in out if x.startswith("R|")]
	if not vals:
		raise TestFailure(f"probe failed: {expr} -> {d.errors[-1:] if d.errors else out}")
	return vals[-1]

def card(code, player=0, loc="LOCATION_MZONE"):
	return f"Duel.GetFirstMatchingCard(Card.IsCode,{player},{loc},0,nil,{code})"

def prompts(d, name, desc=None):
	return [m for m in d.messages if m.name == name and (desc is None or m.data.get("desc") == desc)]

TESTS = []
def test(fn):
	TESTS.append(fn)
	return fn

def run_tests(names=None):
	results = []
	for fn in TESTS:
		if names and fn.__name__ not in names:
			continue
		d = None
		try:
			d = fn()
			errs = d.errors if d else []
			if errs:
				raise TestFailure("engine errors: " + " | ".join(e[:200] for e in errs[:3]))
			if d is not None:
				v = checks.check(d.script_log, DB.custom)
				if v:
					raise TestFailure("rule violations: " + "; ".join(v))
			results.append((fn.__name__, "PASS", ""))
		except TestFailure as e:
			results.append((fn.__name__, "FAIL", str(e)))
		except Exception:
			results.append((fn.__name__, "ERROR", traceback.format_exc(limit=4)))
	return results
