#!/usr/bin/env python3
"""Static checks for EDOPro card scripts.

The CI checker only runs initial_effect. Everything inside condition, cost, target and
operation functions is only executed during a duel, so a misspelled constant or function
there ships silently. This linter resolves every global name against the real runtime
environment and cross-checks the script against its database entry.

Usage:
  lint.py FILE...                 lint scripts (database entry found by passcode)
  lint.py --cdb extra.cdb FILE    also search an extra database
  lint.py --quiet FILE            errors and warnings only (hide style/info notes)
  lint.py --stats DIR             summary counts per rule over a folder (tuning aid)

Levels: E = almost certainly a bug, W = likely wrong or inconsistent with the card text,
S = house-style deviation, I = information worth a look.

Symbol source: <cache>/symbols.tsv produced by `loadcheck.py symbols` (exact runtime
globals). When missing, the linter tries to create it, and falls back to a static index
parsed from the CardScripts Lua files and the ygopro-core C++ bindings.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

NAMESPACES = ["Duel", "Card", "Effect", "Group", "Debug", "aux", "Auxiliary", "Cost", "Fusion", "Synchro",
              "Xyz", "Link", "Ritual", "Pendulum", "Gemini", "Spirit", "Chain", "Maximum", "bit"]
KNOWN_METADATA = {
	"listed_names", "listed_series", "listed_card_types", "material_setcode", "counter_place_list",
	"counter_list", "xyz_number", "roll_dice", "toss_coin", "material", "synchro_nt_required",
	"miracle_synchro_fusion", "synchro_tuner_required", "assault_mode", "fit_monster", "pendulum_level",
	"dark_calling", "self_tuner", "self_equip_trap", "material_trap", "material_race",
	"max_metalmorph_stats", "material_location", "initial_effect",
}
LUA_GLOBALS = {"GetID", "pairs", "ipairs", "next", "select", "type", "tostring", "tonumber", "table",
               "string", "math", "error", "assert", "pcall", "xpcall", "setmetatable", "getmetatable",
               "rawget", "rawset", "rawequal", "rawlen", "load", "self_table", "self_code"}
UNSAFE = {"io", "os", "print", "dofile", "loadfile", "require", "debug", "collectgarbage"}


# ---------------------------------------------------------------- symbols

def load_symbols(allow_build=True) -> tuple[dict[str, str], str]:
	path = C.CACHE_DIR / "symbols.tsv"
	if not path.is_file() and allow_build:
		try:
			subprocess.run([sys.executable, str(Path(__file__).with_name("loadcheck.py")), "symbols"],
			               check=True, capture_output=True, text=True, timeout=900)
		except Exception:
			pass
	static = static_symbols()
	if path.is_file():
		syms = {}
		for line in path.read_text(encoding="utf-8").splitlines():
			parts = line.split("\t")
			if len(parts) >= 2:
				syms[parts[0]] = parts[1]
		# fields initialised to nil in the Lua libraries (e.g. Fusion.SummonEffect) are absent from the dump
		for k, v in static.items():
			syms.setdefault(k, v)
		return syms, f"runtime dump ({path}) + static index"
	return static, "static index only (run loadcheck.py symbols for exact results)"


def definitions_in(path: Path) -> dict[str, str]:
	"""Global names a Lua file defines (functions, fields, UPPER_CASE constants)."""
	out: dict[str, str] = {}
	src = strip_code(C.read_text(path))
	for m in re.finditer(r"\bfunction\s+([A-Za-z_]\w*)[.:](\w+)\s*\(", src):
		out[f"{m.group(1)}.{m.group(2)}"] = "function"
	for m in re.finditer(r"^\s*([A-Za-z_]\w*)\.(\w+)\s*=(?!=)", src, re.M):
		out.setdefault(f"{m.group(1)}.{m.group(2)}", "function")
	for m in re.finditer(r"^([A-Z][A-Za-z0-9_]*)\s*=(?!=)", src, re.M):
		out.setdefault(m.group(1), "number")
	for k in list(out):
		if k.startswith("Auxiliary."):
			out["aux." + k.split(".", 1)[1]] = out[k]
	return out


def static_symbols() -> dict[str, str]:
	syms: dict[str, str] = {}
	files = list(C.SCRIPTS_ROOT.glob("*.lua"))
	extra = C.SCRIPTS_ROOT / "unofficial" / "proc_unofficial.lua"
	if extra.is_file():
		files.append(extra)
	for k in C.parse_constants(files):
		syms[k] = "number"
	for f in files:
		src = strip_code(C.read_text(f))
		for m in re.finditer(r"\bfunction\s+([A-Za-z_]\w*)[.:](\w+)\s*\(", src):
			syms[f"{m.group(1)}.{m.group(2)}"] = "function"
		for m in re.finditer(r"^\s*([A-Za-z_]\w*)\.(\w+)\s*=", src, re.M):
			syms.setdefault(f"{m.group(1)}.{m.group(2)}", "function")
		for m in re.finditer(r"^\s*([A-Z][A-Za-z]*)\s*=\s*\{", src, re.M):
			syms[m.group(1)] = "table"
	libs = {"libcard.cpp": "Card", "libduel.cpp": "Duel", "libeffect.cpp": "Effect",
	        "libgroup.cpp": "Group", "libdebug.cpp": "Debug"}
	for fname, ns in libs.items():
		p = C.CORE_DIR / fname
		if p.is_file():
			for m in re.finditer(r"LUA_(?:STATIC_)?FUNCTION(?:_EXISTING|_ALIAS)?\((\w+)", C.read_text(p)):
				syms[f"{ns}.{m.group(1)}"] = "function"
	for k in list(syms):
		if k.startswith("Auxiliary."):
			syms["aux." + k.split(".", 1)[1]] = syms[k]
	return syms


# ---------------------------------------------------------------- lua lexing

def strip_code(src: str) -> str:
	"""Blank out comments and string contents, keeping offsets and newlines."""
	out = list(src)
	i, n = 0, len(src)

	def blank(a, b):
		for k in range(a, b):
			if out[k] != "\n":
				out[k] = " "

	while i < n:
		ch = src[i]
		if src.startswith("--", i):
			m = re.match(r"--\[(=*)\[", src[i:])
			if m:
				close = "]" + m.group(1) + "]"
				j = src.find(close, i + len(m.group(0)))
				j = n if j < 0 else j + len(close)
			else:
				j = src.find("\n", i)
				j = n if j < 0 else j
			blank(i, j)
			i = j
		elif ch in "\"'":
			j = i + 1
			while j < n and src[j] != ch and src[j] != "\n":
				j += 2 if src[j] == "\\" else 1
			blank(i + 1, min(j, n))
			i = j + 1
		elif ch == "[" and re.match(r"\[(=*)\[", src[i:]):
			m = re.match(r"\[(=*)\[", src[i:])
			close = "]" + m.group(1) + "]"
			j = src.find(close, i + len(m.group(0)))
			j = n if j < 0 else j + len(close)
			blank(i + 1, j - 1)
			i = j
		else:
			i += 1
	return "".join(out)


class Report:
	def __init__(self, path: Path, src: str):
		self.path = path
		self.src = src
		self.items: list[tuple[int, str, str, str]] = []
		self._starts = [0]
		for k, ch in enumerate(src):
			if ch == "\n":
				self._starts.append(k + 1)

	def line_of(self, offset: int) -> int:
		lo, hi = 0, len(self._starts) - 1
		while lo < hi:
			mid = (lo + hi + 1) // 2
			if self._starts[mid] <= offset:
				lo = mid
			else:
				hi = mid - 1
		return lo + 1

	def add(self, level: str, code: str, msg: str, offset: int | None = None, line: int | None = None):
		if line is None:
			line = self.line_of(offset) if offset is not None else 0
		self.items.append((line, level, code, msg))


# ---------------------------------------------------------------- effect blocks

def effect_blocks(code: str):
	"""Yield (var, start, end, text, is_clone) for each effect built in the script."""
	for m in re.finditer(r"\blocal\s+(\w+)\s*=\s*(Effect\.CreateEffect\(|(\w+):Clone\(\))", code):
		var = m.group(1)
		reg = re.search(r"(RegisterEffect\(\s*" + re.escape(var) + r"\b|\breturn\s+" + re.escape(var) + r"\b)",
		                code[m.end():])
		end = m.end() + (reg.end() if reg else 0)
		yield var, m.start(), end, code[m.start():end], m.group(3) is not None


def deprecated_names() -> dict[str, str]:
	p = C.SCRIPTS_ROOT / "deprecated_functions.lua"
	out = {}
	if p.is_file():
		for m in re.finditer(r'make_(deprecated_function_alias|deprecated_function_no_replacement|'
		                     r'deleted_replaced_function|deleted_function)\("([\w.]+)"\s*,\s*"([^"]*)"',
		                     C.read_text(p)):
			name = m.group(2).replace("Auxiliary.", "aux.")
			out[name] = f"{m.group(1).replace('_', ' ')}: {m.group(3)}"
	return out


def edit_distance(a: str, b: str) -> int:
	prev = list(range(len(b) + 1))
	for i, ca in enumerate(a, 1):
		cur = [i]
		for j, cb in enumerate(b, 1):
			cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
		prev = cur
	return prev[-1]


# ---------------------------------------------------------------- lint

class Linter:
	def __init__(self, cdb_extra=(), allow_build=True):
		self.syms, self.sym_source = load_symbols(allow_build)
		self.methods = {k.split(".", 1)[1] for k in self.syms
		                if k.split(".", 1)[0] in ("Card", "Effect", "Group", "Duel") and "." in k}
		self.consts = C.parse_constants()
		self.cards = C.load_cards(cdb_extra)
		self.deprecated = deprecated_names()
		setnames = C.setcode_names(self.consts)
		self.setnames = setnames
		self.extra: dict[str, str] = {}

	def known(self, name: str) -> bool:
		if name in self.syms or name in self.extra:
			return True
		if name.startswith("aux."):
			return "Auxiliary." + name[4:] in self.syms
		if name.startswith("Auxiliary."):
			return "aux." + name[10:] in self.syms
		return False

	def lint(self, path: Path) -> Report:
		raw = path.read_bytes()
		try:
			src = raw.decode("utf-8")
		except UnicodeDecodeError:
			src = raw.decode("utf-8", errors="replace")
		r = Report(path, src)
		if b"\xef\xbf\xbd" in raw or "�" in src and b"\xef\xbf\xbd" not in raw:
			r.add("S", "S070", "file is not valid UTF-8", line=1)
		if b"\r\n" in raw:
			r.add("S", "S070", "CRLF line endings (repository uses LF)", line=1)
		for no, line in enumerate(src.splitlines(), 1):
			if line != line.rstrip():
				r.add("S", "S070", "trailing whitespace", line=no)
			if re.match(r"^ {2,}\S", line):
				r.add("S", "S070", "indentation uses spaces (repository uses tabs)", line=no)
		code = strip_code(src)
		self.extra = {}
		deck_master = C.SCRIPTS_ROOT / "unofficial" / "c153000000.lua"
		if path.parent.name == "unofficial" and deck_master.is_file():
			self.extra.update(definitions_in(deck_master))  # Deck Master mode helpers
		for lm in re.finditer(r'Duel\.LoadScript\(\s*"([^"]+)"', src):
			for base in (C.SCRIPTS_ROOT, path.parent, C.SCRIPTS_ROOT / "unofficial"):
				f = base / lm.group(1)
				if f.is_file():
					self.extra.update(definitions_in(f))
					break
		m = re.fullmatch(r"c(\d+)\.lua", path.name)
		cid = int(m.group(1)) if m else None
		if cid is None:
			r.add("E", "E003", "file name must be cPASSCODE.lua", line=1)
		card = self.cards.get(cid, [None])[0] if cid else None
		self.check_header(r, src, code, card)
		self.check_names(r, code)
		self.check_s_members(r, code)
		self.check_effects(r, code, card)
		if card:
			self.check_strings(r, code, card)
			self.check_text_consistency(r, code, card)
		elif cid:
			r.add("I", "I001", f"passcode {cid} not found in any database; database checks skipped", line=1)
		self.check_style(r, code)
		r.items.sort()
		return r

	# -- header
	def check_header(self, r, src, code, card):
		lines = src.splitlines()
		if re.search(r"^Duel\.LoadCardScript(Alias)?\(", code, re.M):
			return  # alternate-artwork stub that loads another card's script
		if not re.search(r"^local\s+\w+\s*,\s*\w+\s*(,\s*\w+\s*)*=\s*GetID\(\)", code, re.M):
			r.add("E", "E001", "missing `local s,id=GetID()`", line=1)
		elif not re.search(r"^local\s+s\s*,\s*id\s*(,\s*\w+\s*)*=\s*GetID\(\)", code, re.M):
			r.add("S", "S071", "house style names the GetID() results `s,id`", line=1)
		if not re.search(r"^function\s+\w+\.initial_effect\s*\(\s*\w+\s*\)", code, re.M):
			r.add("E", "E002", "missing `function s.initial_effect(c)`", line=1)
		if len(lines) < 2 or not lines[0].startswith("--") or not lines[1].startswith("--"):
			r.add("S", "S071", "header should be: --<Japanese name> / --<English name> [/ --scripted by ...]", line=1)
		elif card and lines[1][2:].strip() != card.name:
			r.add("S", "S071", f"line 2 should be the database name: --{card.name}", line=2)

	# -- globals and namespaces
	def check_names(self, r, code):
		local_defs = set(re.findall(r"\blocal\s+([A-Za-z_]\w*)", code))
		local_defs |= set(re.findall(r"^\s*([A-Z][A-Z0-9_]+)\s*=", code, re.M))
		local_defs |= set(re.findall(r"\blocal\s+function\s+(\w+)", code))
		script_defs = {f"{a}.{b}" for a, b in re.findall(r"\bfunction\s+(\w+)[.:](\w+)\s*\(", code)}
		for m in re.finditer(r"(?<![.:\w])(" + "|".join(NAMESPACES) + r")\.([A-Za-z_]\w*)", code):
			name = f"{m.group(1)}.{m.group(2)}"
			if m.group(1) in local_defs:
				continue
			if name in script_defs or re.match(r"\s*=(?!=)", code[m.end():]):
				continue  # the script defines it
			if name in self.deprecated:
				r.add("W", "W021", f"{name} is deprecated ({self.deprecated[name]})", m.start())
			elif not self.known(name):
				r.add("E", "E010", f"unknown function/field {name}", m.start())
		for m in re.finditer(r"(?<![.:\w])([A-Z][A-Z0-9]*_[A-Z0-9_]+)\b", code):
			name = m.group(1)
			if name in local_defs or name in self.syms or name in self.extra:
				continue
			r.add("E", "E011", f"unknown constant {name}", m.start())
		for m in re.finditer(r":([A-Z]\w*)\s*\(", code):
			meth = m.group(1)
			if meth not in self.methods and not any(k.endswith("." + meth) for k in self.extra):
				r.add("W", "W020", f"method :{meth}() does not exist on Card/Effect/Group", m.start())
		for m in re.finditer(r"(?<![.:\w])(" + "|".join(UNSAFE) + r")\b\s*[.(]", code):
			if m.group(1) not in local_defs:
				r.add("W", "W080", f"`{m.group(1)}` is not available to scripts in the client", m.start())

	# -- s.members
	def check_s_members(self, r, code):
		defined = set(re.findall(r"\bfunction\s+s[.:](\w+)\s*\(", code))
		defined |= set(re.findall(r"(?<![\w.])s\.(\w+)\s*=(?!=)", code))
		for m in re.finditer(r"(?<![\w.])s\.(\w+)", code):
			name = m.group(1)
			if name in defined:
				continue
			r.add("E", "E012", f"s.{name} is used but never defined in this script", m.start())
		for m in re.finditer(r"^s\.(\w+)\s*=", code, re.M):
			name = m.group(1)
			if name in KNOWN_METADATA:
				continue
			close = [k for k in KNOWN_METADATA if edit_distance(name, k) <= 2]
			if close:
				r.add("W", "W051", f"s.{name} looks like a typo of s.{close[0]}", m.start())

	# -- effects
	def check_effects(self, r, code, card):
		persistent_st = False
		if card:
			t = card.type
			persistent_st = bool(t & (self.consts["TYPE_SPELL"] | self.consts["TYPE_TRAP"])) and bool(
				t & (self.consts["TYPE_CONTINUOUS"] | self.consts["TYPE_FIELD"] | self.consts["TYPE_EQUIP"]
				     | self.consts["TYPE_PENDULUM"]))
		init = re.search(r"^function\s+s\.initial_effect.*?^end\b", code, re.M | re.S)
		for var, start, end, text, is_clone in effect_blocks(code):
			if is_clone:
				continue
			tm = re.search(r":SetType\(([^)]*)\)", text)
			if not tm:
				continue
			etype = tm.group(1)
			activated = re.search(r"EFFECT_TYPE_(IGNITION|TRIGGER_O|TRIGGER_F|QUICK_O|QUICK_F|FLIP|ACTIVATE)", etype)
			in_init = init and init.start() <= start < init.end()
			if activated and in_init and ":SetDescription(" not in text:
				is_activate = "EFFECT_TYPE_ACTIVATE" in etype
				bare_activation = is_activate and ":SetOperation(" not in text and ":SetTarget(" not in text
				if not (is_activate and (persistent_st or bare_activation)):
					r.add("S", "S040", f"activated effect {var} has no SetDescription (MODERNIZING.md)", start)
			if "SINGLE" in etype and "TRIGGER" in etype and "EFFECT_FLAG_DAMAGE_STEP" in text:
				r.add("I", "I041", f"{var}: SINGLE trigger with EFFECT_FLAG_DAMAGE_STEP; the core already allows "
				                   "the Damage Step for these unless a ruling says otherwise", start)
			if "TRIGGER_F" in etype and "EFFECT_FLAG_DELAY" in text:
				r.add("I", "I042", f"{var}: mandatory trigger with EFFECT_FLAG_DELAY (mandatory triggers cannot "
				                   "miss timing; the flag is usually unnecessary)", start)
		has_select_target = re.search(r"Duel\.SelectTarget\b", code)
		has_flag = "EFFECT_FLAG_CARD_TARGET" in code or re.search(r"aux\.Add(Equip|Persistent)Procedure", code)
		if has_select_target and not has_flag:
			r.add("W", "W043", "selects targets but no effect has EFFECT_FLAG_CARD_TARGET", has_select_target.start())
		for fm in re.finditer(r"^function\s+s\.(\w+)\s*\(([^)]*)\)(.*?)^end\b", code, re.M | re.S):
			params, body = fm.group(2), fm.group(3)
			if "Duel.SelectTarget" in body and "chkc" not in params:
				r.add("W", "W044", f"s.{fm.group(1)} selects targets but has no chkc parameter/handling", fm.start())
			elif "Duel.SelectTarget" in body and "chkc" in params and "if chkc then" not in body:
				r.add("I", "I044", f"s.{fm.group(1)}: chkc is never checked (`if chkc then return ... end`)", fm.start())

	# -- strings
	def check_strings(self, r, code, card):
		used = set()
		for m in re.finditer(r"aux\.Stringid\(\s*id\s*,\s*(\d+)\s*\)", code):
			n = int(m.group(1))
			used.add(n)
			if n > 15:
				r.add("E", "E030", f"aux.Stringid index {n} is out of range (0-15)", m.start())
			elif not card.strings[n]:
				r.add("W", "W030", f"aux.Stringid(id,{n}) -> str{n + 1} is empty in {card.db}", m.start())
		unused = [i for i, s in enumerate(card.strings) if s and i not in used]
		if unused and used:
			r.add("I", "I031", "database strings never referenced with aux.Stringid(id,N): "
			      + ", ".join(f"{i}" for i in unused), line=1)

	# -- text vs code
	def check_text_consistency(self, r, code, card):
		text, name = card.desc, card.name
		qn = re.escape(f'"{name}"')
		limits = re.findall(r"SetCountLimit\(([^)]*)\)", code)
		hard = [x for x in limits if re.search(r"\bid\b", x)]
		if re.search(r"You can only use each effect of " + qn + r" once per turn", text):
			if len(hard) >= 2 and all(re.fullmatch(r"\s*1\s*,\s*id\s*", x) for x in hard):
				r.add("W", "W041", "text says 'each effect ... once per turn' but every limit is SetCountLimit(1,id); "
				      "use {id,0}, {id,1}, ... for separate counters", line=1)
		if re.search(r"You can only activate 1 " + qn + r" per turn", text) and "EFFECT_COUNT_CODE_OATH" not in code:
			r.add("W", "W041", "text says 'You can only activate 1 ... per turn' but no EFFECT_COUNT_CODE_OATH", line=1)
		if re.search(r"once per Duel", text) and "EFFECT_COUNT_CODE_DUEL" not in code:
			r.add("W", "W041", "text mentions 'once per Duel' but no EFFECT_COUNT_CODE_DUEL", line=1)
		if re.search(r"You can only Special Summon " + qn + r" once per turn\.", text) and "SetSPSummonOnce" not in code:
			r.add("W", "W041", "text restricts Special Summons of this card per turn but no c:SetSPSummonOnce(id)", line=1)
		if re.search(r"You can only control 1 " + qn, text) and "SetUniqueOnField" not in code:
			r.add("W", "W041", "text says 'You can only control 1' but no c:SetUniqueOnField(1,0,id)", line=1)
		if re.search(r'except "' + re.escape(name) + '"', text) and not re.search(
				r"s\.listed_names\s*=\s*\{[^}]*\bid\b", code):
			r.add("I", "I050", "text says except its own name; house style adds id to s.listed_names", line=1)
		others = {q for q in re.findall(r'"([^"]+)"', text) if q != name}
		if others and "s.listed_names" not in code and "s.listed_series" not in code:
			r.add("I", "I050", "text quotes other names/archetypes (" + ", ".join(sorted(others))[:80]
			      + ") but the script has no s.listed_names / s.listed_series", line=1)
		if re.search(r"\btarget", text, re.I) and "EFFECT_FLAG_CARD_TARGET" not in code and not re.search(
				r"SetTargetRange|SetTarget\(", code):
			r.add("I", "I043", "text mentions targeting but no EFFECT_FLAG_CARD_TARGET", line=1)

	# -- style
	def check_style(self, r, code):
		for m in re.finditer(r"\b(LOCATION|RESET|REASON|RACE|TIMING|PHASE)_[A-Z_]+\s*\+\s*(LOCATION|RESET|REASON|RACE|"
		                     r"TIMING|PHASE|RESETS)_", code):
			r.add("S", "S060", "combine bit flags with | (house style: + only for EFFECT_TYPE/CATEGORY/EFFECT_FLAG)",
			      m.start())
		for m in re.finditer(r":GetCount\(\)", code):
			r.add("S", "S061", "prefer #g over g:GetCount()", m.start())
		mandatory = re.search(r"EFFECT_TYPE_(TRIGGER_F|FLIP|QUICK_F)", code)
		for m in ([] if mandatory else re.finditer(r"if\s+tc\s+and\s+tc:IsRelateToEffect\(e\)", code)):
			r.add("I", "I062", "`if tc and` is only needed for mandatory triggers (MODERNIZING.md)", m.start())
		for m in re.finditer(r"IsSetCard\((0x[0-9a-fA-F]+)", code):
			val = int(m.group(1), 16)
			names = self.setnames.get(val)
			hint = f" -> {names[0]}" if names else " (add a SET_ constant)"
			r.add("S", "S063", f"hardcoded setcode {m.group(1)}{hint}", m.start())
		for m in re.finditer(r"listed_series\s*=\s*\{[^}]*0x[0-9a-fA-F]+", code):
			r.add("S", "S063", "hardcoded setcode in s.listed_series; use SET_ constants", m.start())


def format_report(r: Report, quiet: bool, root: Path) -> list[str]:
	out = []
	try:
		rel = r.path.resolve().relative_to(root)
	except ValueError:
		rel = r.path
	for line, level, code, msg in r.items:
		if quiet and level in ("S", "I"):
			continue
		out.append(f"{rel}:{line}: {level} {code} {msg}")
	return out


def main(argv=None):
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("paths", nargs="+", help="script files or folders")
	ap.add_argument("--cdb", action="append", default=[], help="extra .cdb file or folder")
	ap.add_argument("--quiet", action="store_true", help="only E and W")
	ap.add_argument("--stats", action="store_true", help="print counts per rule instead of findings")
	ap.add_argument("--no-build", action="store_true", help="never build the runtime symbol dump")
	args = ap.parse_args(argv)
	files = []
	for p in map(Path, args.paths):
		files.extend(sorted(p.glob("c*.lua")) if p.is_dir() else [p])
	linter = Linter(args.cdb, allow_build=not args.no_build)
	print(f"symbols: {linter.sym_source}", file=sys.stderr)
	counts: Counter = Counter()
	files_with: Counter = Counter()
	worst = 0
	for f in files:
		rep = linter.lint(f)
		seen = set()
		for _, level, code, _ in rep.items:
			counts[(level, code)] += 1
			if code not in seen:
				files_with[(level, code)] += 1
				seen.add(code)
			if level == "E":
				worst = max(worst, 2)
			elif level == "W":
				worst = max(worst, 1)
		if not args.stats:
			for line in format_report(rep, args.quiet, C.SCRIPTS_ROOT):
				print(line)
	if args.stats:
		print(f"{len(files)} files")
		for (level, code), n in sorted(counts.items()):
			print(f"{level} {code}: {n} findings in {files_with[(level, code)]} files")
	else:
		e = sum(n for (lv, _), n in counts.items() if lv == "E")
		w = sum(n for (lv, _), n in counts.items() if lv == "W")
		print(f"-- {len(files)} file(s): {e} error(s), {w} warning(s)", file=sys.stderr)
	return 1 if worst == 2 else 0


if __name__ == "__main__":
	sys.exit(main())
