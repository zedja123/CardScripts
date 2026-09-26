"""Shared helpers for the EDOPro card-scripting tools.

Standard library only. Locates the sibling repositories, parses the Lua
constant files, reads every card database and decodes the packed fields.

Paths can be overridden with environment variables:
  EDOPRO_SCRIPTS  CardScripts checkout (default: the repo containing this skill)
  EDOPRO_CDB      extra .cdb files or folders, separated by os.pathsep
  EDOPRO_CORE     ygopro-core checkout (default: <workspace>/ygopro-core)
  EDOPRO_CACHE    cache folder for the built checker (default: ~/.cache/edopro-card-scripting)
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent


def _find_scripts_root() -> Path:
	env = os.environ.get("EDOPRO_SCRIPTS")
	if env:
		return Path(env).resolve()
	for parent in SKILL_DIR.parents:
		if (parent / "constant.lua").is_file() and (parent / "utility.lua").is_file():
			return parent
	sys.exit("common.py: cannot find the CardScripts root (set EDOPRO_SCRIPTS)")


SCRIPTS_ROOT = _find_scripts_root()
WORKSPACE = SCRIPTS_ROOT.parent
CORE_DIR = Path(os.environ.get("EDOPRO_CORE", WORKSPACE / "ygopro-core"))
SCRAPIYARD_DIR = Path(os.environ.get("EDOPRO_SCRAPIYARD", WORKSPACE / "scrapiyard"))
CACHE_DIR = Path(os.environ.get("EDOPRO_CACHE", Path.home() / ".cache" / "edopro-card-scripting"))
SCRIPT_FOLDERS = ["official", "pre-release", "pre-errata", "unofficial", "goat", "rush", "skill"]


# ---------------------------------------------------------------- databases

def cdb_paths(extra=()) -> list[Path]:
	"""All .cdb files: sibling BabelCDB* folders, EDOPRO_CDB entries, and extra args."""
	found: list[Path] = []
	sources: list[Path] = []
	for d in sorted(WORKSPACE.iterdir()):
		if d.is_dir() and d.name.lower().startswith("babelcdb"):
			sources.append(d)
	for item in os.environ.get("EDOPRO_CDB", "").split(os.pathsep):
		if item:
			sources.append(Path(item))
	sources.extend(Path(x) for x in extra)
	for src in sources:
		if src.is_dir():
			found.extend(sorted(src.glob("*.cdb")))
		elif src.is_file():
			found.append(src)
	seen, out = set(), []
	for p in found:
		rp = p.resolve()
		if rp not in seen:
			seen.add(rp)
			out.append(p)
	return out


class Card:
	__slots__ = ("id", "ot", "alias", "setcode", "type", "atk", "def_", "level", "race",
	             "attribute", "category", "name", "desc", "strings", "db")

	def __init__(self, row, db):
		(self.id, self.ot, self.alias, self.setcode, self.type, self.atk, self.def_, self.level,
		 self.race, self.attribute, self.category, self.name, self.desc) = row[:13]
		self.strings = [s or "" for s in row[13:29]]
		self.desc = self.desc or ""
		self.name = self.name or ""
		self.db = db


_CARD_SQL = ('select d.id,d.ot,d.alias,d.setcode,d.type,d.atk,d.def,d.level,d.race,d.attribute,'
             'd.category,t.name,t."desc",' + ",".join(f"t.str{i}" for i in range(1, 17)) +
             " from datas d join texts t on d.id=t.id")


def load_cards(extra=()) -> dict[int, list[Card]]:
	"""id -> list of Card (one per database that contains it, in load order)."""
	cards: dict[int, list[Card]] = {}
	for db in cdb_paths(extra):
		try:
			con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
			for row in con.execute(_CARD_SQL):
				cards.setdefault(row[0], []).append(Card(row, db.name))
			con.close()
		except sqlite3.Error as exc:
			print(f"warning: cannot read {db}: {exc}", file=sys.stderr)
	return cards


# ---------------------------------------------------------------- scripts

def script_index(extra_dirs=()) -> dict[int, list[Path]]:
	"""passcode -> script paths found in the CardScripts folders (and extra dirs)."""
	idx: dict[int, list[Path]] = {}
	dirs = [SCRIPTS_ROOT / f for f in SCRIPT_FOLDERS] + [Path(d) for d in extra_dirs]
	for d in dirs:
		if not d.is_dir():
			continue
		for p in d.glob("c*.lua"):
			m = re.fullmatch(r"c(\d+)\.lua", p.name)
			if m:
				idx.setdefault(int(m.group(1)), []).append(p)
	return idx


def read_text(p: Path) -> str:
	return p.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------- constants

_ASSIGN = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*([^\n]+?)\s*(?:--.*)?$", re.M)
_SAFE_EXPR = re.compile(r"^[0-9a-fA-Fx\s|&~+\-*()<>]+$")


def _eval_expr(expr: str, env: dict[str, int]):
	def sub(m):
		name = m.group(0)
		if name in env:
			return str(env[name])
		raise KeyError(name)
	try:
		e = re.sub(r"\b[A-Z][A-Z0-9_]*\b", sub, expr)
	except KeyError:
		return None
	if not _SAFE_EXPR.match(e):
		return None
	try:
		return int(eval(e, {"__builtins__": {}}, {}))  # noqa: S307 - restricted charset
	except Exception:
		return None


def parse_constants(files=None) -> dict[str, int]:
	"""Global UPPER_CASE integer constants defined in the root Lua files."""
	if files is None:
		files = sorted(SCRIPTS_ROOT.glob("*.lua"))
	env: dict[str, int] = {}
	pending = []
	for f in files:
		for m in _ASSIGN.finditer(read_text(Path(f))):
			pending.append((m.group(1), m.group(2)))
	for _ in range(4):  # a few passes resolve forward references
		rest = []
		for name, expr in pending:
			v = _eval_expr(expr, env)
			if v is None:
				rest.append((name, expr))
			else:
				env[name] = v
		pending = rest
	return env


def constants_by_prefix(consts: dict[str, int], prefix: str) -> dict[str, int]:
	return {k: v for k, v in consts.items() if k.startswith(prefix)}


# ---------------------------------------------------------------- decoding

OT_NAMES = [  # EDOPro "scope" bits (the ot column)
	(0x1, "OCG"), (0x2, "TCG"), (0x4, "Anime"), (0x8, "Illegal"), (0x10, "Video Game"),
	(0x20, "Custom"), (0x40, "Speed"), (0x100, "Pre-release"), (0x200, "Rush"),
	(0x400, "Legend"), (0x1000, "Hidden"),
]

LINK_MARKERS = [
	(0x40, "TL"), (0x80, "T"), (0x100, "TR"), (0x8, "L"), (0x20, "R"),
	(0x1, "BL"), (0x2, "B"), (0x4, "BR"),
]


def bits_to_names(value: int, table: dict[str, int], prefix: str, skip=()) -> list[str]:
	out = []
	for name, bit in sorted(table.items(), key=lambda kv: kv[1]):
		if name in skip or bit == 0 or bit & (bit - 1):
			continue  # only single-bit constants
		if value & bit:
			out.append(name[len(prefix):])
	return out


def decode_ot(ot: int) -> str:
	names = [n for b, n in OT_NAMES if ot & b]
	return "+".join(names) if names else "none"


def split_setcodes(setcode: int) -> list[int]:
	out = []
	while setcode:
		sc = setcode & 0xFFFF
		if sc:
			out.append(sc)
		setcode >>= 16
	return out


def setcode_names(consts: dict[str, int]) -> dict[int, list[str]]:
	rev: dict[int, list[str]] = {}
	for k, v in consts.items():
		if k.startswith("SET_"):
			rev.setdefault(v, []).append(k)
	return rev


def decode_level(card: Card):
	lv = card.level & 0xFF
	lscale = (card.level >> 24) & 0xFF
	rscale = (card.level >> 16) & 0xFF
	return lv, lscale, rscale


def decode_markers(value: int) -> str:
	return " ".join(n for b, n in LINK_MARKERS if value & b) or "-"


def fmt_stat(v: int) -> str:
	return "?" if v == -2 else str(v)


def describe(card: Card, consts: dict[str, int], setnames: dict[int, list[str]]) -> str:
	types = constants_by_prefix(consts, "TYPE_")
	races = constants_by_prefix(consts, "RACE_")
	attrs = constants_by_prefix(consts, "ATTRIBUTE_")
	tnames = bits_to_names(card.type, types, "TYPE_", skip={"TYPE_EXTRA", "TYPES_TOKEN", "TYPE_PLUSMINUS"})
	lines = [f"{card.id}  {card.name}   [{card.db}]"]
	lines.append(f"  scope(ot)={hex(card.ot)} ({decode_ot(card.ot)})  alias={card.alias or '-'}"
	              f"  type={hex(card.type)} ({'|'.join(tnames)})")
	if card.type & consts.get("TYPE_MONSTER", 1):
		lv, ls, rs = decode_level(card)
		rname = "|".join(bits_to_names(card.race, races, "RACE_", skip={"RACE_ALL", "RACES_BEAST_BWARRIOR_WINGB"})) or hex(card.race)
		aname = "|".join(bits_to_names(card.attribute, attrs, "ATTRIBUTE_", skip={"ATTRIBUTE_ALL"})) or hex(card.attribute)
		if card.type & consts.get("TYPE_LINK", 0x4000000):
			stat = f"Link-{lv}  ATK {fmt_stat(card.atk)}  markers: {decode_markers(card.def_)} ({hex(card.def_)})"
		elif card.type & consts.get("TYPE_XYZ", 0x800000):
			stat = f"Rank {lv}  ATK {fmt_stat(card.atk)} / DEF {fmt_stat(card.def_)}"
		else:
			stat = f"Level {lv}  ATK {fmt_stat(card.atk)} / DEF {fmt_stat(card.def_)}"
		if card.type & consts.get("TYPE_PENDULUM", 0x1000000):
			stat += f"  scales {ls}/{rs}"
		lines.append(f"  {aname} {rname}  {stat}")
	if card.setcode:
		parts = []
		for sc in split_setcodes(card.setcode):
			parts.append(f"{hex(sc)}={'/'.join(setnames.get(sc, ['(no SET_ constant)']))}")
		lines.append("  archetypes: " + ", ".join(parts))
	if card.category:
		lines.append(f"  deck-edit category bits: {hex(card.category)} (search filter only; not script categories)")
	return "\n".join(lines)


def strings_block(card: Card) -> str:
	out = []
	for i, s in enumerate(card.strings):
		if s:
			out.append(f"  aux.Stringid(id,{i}) = str{i + 1}: {s}")
	return "\n".join(out) if out else "  (no strings)"


def resolve_cards(arg: str, cards: dict[int, list[Card]]) -> list[Card]:
	"""Accept a passcode, an exact name, or a case-insensitive name substring."""
	if arg.isdigit():
		return cards.get(int(arg), [])
	low = arg.lower()
	exact = [cs[0] for cs in cards.values() if cs[0].name.lower() == low]
	if exact:
		return exact
	return [cs[0] for cs in cards.values() if low in cs[0].name.lower()]
