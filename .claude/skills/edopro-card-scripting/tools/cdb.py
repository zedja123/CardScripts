#!/usr/bin/env python3
"""Card database helper for EDOPro scripting.

Commands:
  show     ID|NAME ...          decoded card data, strings (aux.Stringid map) and script paths
  search   REGEX                find cards whose text/name matches; filter by script folder/code
  analogs  ID|NAME | --text T   for each effect clause, list scripted cards with the most similar wording
  archetype NAME|HEX            SET_ constants matching a name or value, with card counts
  new      SPEC.json            build a datas/texts row from a readable spec (dry run unless --write)
  puzzle   [opp:]ZONE:ID ...    write an EDOPro puzzle that sets up a test board

Examples:
  cdb.py show 101402082
  cdb.py show "Ash Blossom"
  cdb.py search 'banish it until the End Phase' --folder official --code 'RemoveUntil' --limit 5
  cdb.py analogs 101402088 --top 3
  cdb.py analogs --text 'If this card is sent to the GY: You can target 1 Spell in your GY; add it to your hand.'
  cdb.py archetype "Raise Moon"
  cdb.py new mycard.json --db ../BabelCDBZedja/cards-custom.cdb --write
  cdb.py puzzle hand:101402082 deck:101402082 opp:szone:"Mirror Force" -o test.lua
"""
from __future__ import annotations

import argparse
import json
import signal
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def cmd_show(args):
	cards = C.load_cards(args.cdb)
	consts = C.parse_constants()
	setnames = C.setcode_names(consts)
	scripts = C.script_index(args.scripts)
	rc = 0
	for a in args.cards:
		hits = C.resolve_cards(a, cards)
		if not hits:
			print(f"{a}: not found in {len(C.cdb_paths(args.cdb))} databases")
			rc = 1
			continue
		alts = [c for c in hits if c.alias and any(h.id == c.alias for h in hits)]
		if alts and not a.isdigit():
			print(f"{a}: skipping alternate artworks {', '.join(str(c.id) for c in alts)}")
			hits = [c for c in hits if c not in alts]
		if len(hits) > 12:
			print(f"{a}: {len(hits)} matches, showing 12 (use a passcode or the exact name)")
			hits = hits[:12]
		for card in hits:
			print("=" * 100)
			print(C.describe(card, consts, setnames))
			others = [c.db for c in cards[card.id] if c is not card]
			if others:
				print(f"  also present in: {', '.join(others)}")
			print("  text:")
			for line in card.desc.splitlines():
				print("    " + line)
			print("  strings:")
			print(C.strings_block(card))
			paths = scripts.get(card.id, [])
			if card.alias and not paths and scripts.get(card.alias):
				print(f"  script: uses alias {card.alias} -> {', '.join(str(p) for p in scripts[card.alias])}")
			else:
				print("  script: " + (", ".join(str(p) for p in paths) if paths else "NOT SCRIPTED"))
			if args.source and paths:
				print("-" * 100)
				print(C.read_text(paths[0]))
	return rc


def _folder_of(p: Path) -> str:
	return p.parent.name


def cmd_search(args):
	cards = C.load_cards(args.cdb)
	scripts = C.script_index(args.scripts)
	flags = re.I | re.S
	rx = re.compile(args.regex, flags)
	code_rx = re.compile(args.code, re.S) if args.code else None
	consts = C.parse_constants()
	type_mask = 0
	for t in args.type or []:
		type_mask |= consts.get("TYPE_" + t.upper(), 0)
	shown = total = 0
	for cid in sorted(cards, reverse=not args.oldest):
		card = cards[cid][0]
		hay = card.name if args.name else card.desc if args.text_only else card.name + "\n" + card.desc
		if not rx.search(hay):
			continue
		if type_mask and not (card.type & type_mask) == type_mask:
			continue
		paths = scripts.get(cid, [])
		if args.folder:
			paths = [p for p in paths if _folder_of(p) in args.folder]
			if not paths:
				continue
		if args.unscripted and paths:
			continue
		if code_rx and not any(code_rx.search(C.read_text(p)) for p in paths):
			continue
		total += 1
		if shown < args.limit:
			shown += 1
			where = ", ".join(str(p.relative_to(C.SCRIPTS_ROOT)) for p in paths) or "NOT SCRIPTED"
			print(f"{cid:>10}  {card.name}  ->  {where}")
			if args.context:
				m = rx.search(card.desc)
				if m:
					s = max(0, m.start() - args.context)
					print("            ..." + card.desc[s:m.end() + args.context].replace("\n", " ") + "...")
	print(f"-- {total} match(es){'' if total <= shown else f', {shown} shown (raise --limit)'}")
	return 0


# ---------------------------------------------------------------- analogs

_OPT = re.compile(r"You can only (use|activate)[^.]*?(once per turn|per turn|once per Duel|once that turn)[^.]*\.", re.I)
_QUOTED = re.compile(r'"[^"]*"')
_WORD = re.compile(r"[a-z]+|[0-9]+|[:;(),]")


def split_clauses(text: str) -> list[str]:
	text = _OPT.sub("", text.replace("\r", ""))
	parts = []
	for line in text.split("\n"):
		line = line.strip(" ●")
		if not line or line.startswith("["):
			continue
		for sent in re.split(r"(?<=[.])\s+(?=[A-Z(\"●])", line):
			sent = sent.strip()
			if len(sent) > 12:
				parts.append(sent)
	return parts


def normalize(clause: str) -> list[str]:
	s = _QUOTED.sub(" qname ", clause.lower())
	s = re.sub(r"\b\d+\b", " num ", s)
	return _WORD.findall(s)


def features(tokens: list[str]) -> set[str]:
	f = set()
	for n in (2, 3):
		for i in range(len(tokens) - n + 1):
			f.add(" ".join(tokens[i:i + n]))
	return f


def best_comment_line(src: str, clause: str) -> int | None:
	key = re.sub(r"\s+", " ", clause.rstrip("."))[:48].lower()
	for no, line in enumerate(src.splitlines(), 1):
		if line.strip().startswith("--") and key[:32] in line.lower():
			return no
	return None


def cmd_analogs(args):
	cards = C.load_cards(args.cdb)
	scripts = C.script_index(args.scripts)
	if args.text:
		query_text, self_id = args.text, None
	else:
		hits = C.resolve_cards(args.card, cards)
		if not hits:
			print(f"{args.card}: not found")
			return 1
		query_text, self_id = hits[0].desc, hits[0].id
		print(f"{hits[0].id} {hits[0].name}")
	folders = set(args.folder)
	# build the clause index over scripted cards in the chosen folders
	clauses: list[tuple[int, str, set[str]]] = []
	inv: dict[str, list[int]] = defaultdict(list)
	for cid, paths in scripts.items():
		if cid == self_id or cid not in cards:
			continue
		if not any(_folder_of(p) in folders for p in paths):
			continue
		for cl in split_clauses(cards[cid][0].desc):
			feats = features(normalize(cl))
			if not feats:
				continue
			k = len(clauses)
			clauses.append((cid, cl, feats))
			for f in feats:
				inv[f].append(k)
	for qc in split_clauses(query_text):
		qf = features(normalize(qc))
		if not qf:
			continue
		score: dict[int, int] = defaultdict(int)
		for f in qf:
			for k in inv.get(f, ()):
				score[k] += 1
		ranked = []
		for k, inter in score.items():
			cf = clauses[k][2]
			sim = inter / (len(qf) + len(cf) - inter)
			ranked.append((sim, k))
		ranked.sort(reverse=True)
		print("\n" + "#" * 100)
		print("CLAUSE: " + qc)
		seen = set()
		for sim, k in ranked:
			cid, cl, _ = clauses[k]
			if cid in seen:
				continue
			seen.add(cid)
			path = [p for p in scripts[cid] if _folder_of(p) in folders][0]
			line = best_comment_line(C.read_text(path), cl) if args.lines else None
			loc = f"{path.relative_to(C.SCRIPTS_ROOT)}" + (f":{line}" if line else "")
			print(f"  {sim:.2f}  {cid} {cards[cid][0].name}  ->  {loc}")
			print(f"        {cl[:220]}")
			if len(seen) >= args.top:
				break
	return 0


# ---------------------------------------------------------------- archetypes

def cmd_archetype(args):
	consts = C.parse_constants()
	cards = C.load_cards(args.cdb)
	sets = C.constants_by_prefix(consts, "SET_")
	q = args.query
	if re.fullmatch(r"0x[0-9a-fA-F]+|\d+", q):
		val = int(q, 0)
		matches = {k: v for k, v in sets.items() if v == val}
		if not matches:
			print(f"no SET_ constant equals {hex(val)}")
			matches = {f"(unnamed {hex(val)})": val}
	else:
		key = re.sub(r"[^A-Z0-9]+", "_", q.upper()).strip("_")
		matches = {k: v for k, v in sets.items() if key in k}
	for name, val in sorted(matches.items(), key=lambda kv: kv[1]):
		base, sub = val & 0xFFF, val >> 12
		n = 0
		for cs in cards.values():
			for sc in C.split_setcodes(cs[0].setcode):
				if sc & 0xFFF == base and (sc >> 12) & sub == sub:
					n += 1
					break
		print(f"{name:40s} {hex(val):8s} cards matching IsSetCard: {n}")
	if not matches:
		print("no match; archetype constants live in archetype_setcode_constants.lua")
	return 0


# ---------------------------------------------------------------- new entries

def _names_to_bits(values, consts, prefix, what):
	if isinstance(values, int):
		return values
	if isinstance(values, str):
		if re.fullmatch(r"0x[0-9a-fA-F]+|\d+", values):
			return int(values, 0)
		values = re.split(r"[|,+ ]+", values)
	out = 0
	for v in values:
		if isinstance(v, int):
			out |= v
			continue
		key = prefix + re.sub(r"[^A-Z0-9]+", "", v.upper())
		cand = {k.replace("_", ""): val for k, val in consts.items() if k.startswith(prefix)}
		norm = key.replace("_", "")
		if norm not in cand:
			sys.exit(f"unknown {what}: {v}")
		out |= cand[norm]
	return out


def build_row(spec: dict, consts: dict[str, int]):
	ot_map = {n.lower().replace(" ", "").replace("-", ""): b for b, n in C.OT_NAMES}
	ot = spec.get("ot", "custom")
	if isinstance(ot, (list, str)) and not (isinstance(ot, str) and re.fullmatch(r"0x[0-9a-fA-F]+|\d+", ot)):
		items = [ot] if isinstance(ot, str) else ot
		v = 0
		for it in items:
			k = it.lower().replace(" ", "").replace("-", "")
			if k not in ot_map:
				sys.exit(f"unknown scope/ot: {it} (known: {', '.join(n for _, n in C.OT_NAMES)})")
			v |= ot_map[k]
		ot = v
	elif isinstance(ot, str):
		ot = int(ot, 0)
	ctype = _names_to_bits(spec["type"], consts, "TYPE_", "type")
	setcode = 0
	for i, sc in enumerate(spec.get("setcodes", [])[:4]):
		if isinstance(sc, str) and sc.startswith("SET_"):
			if sc not in consts:
				sys.exit(f"unknown archetype constant {sc}")
			val = consts[sc]
		else:
			val = int(sc, 0) if isinstance(sc, str) else sc
		setcode |= (val & 0xFFFF) << (16 * i)
	is_monster = bool(ctype & consts["TYPE_MONSTER"])
	level = atk = df = race = attr = 0
	if is_monster:
		level = int(spec.get("level", spec.get("rank", spec.get("link", 0))))
		if ctype & consts["TYPE_PENDULUM"]:
			ls = int(spec.get("lscale", spec.get("scale", 0)))
			rs = int(spec.get("rscale", spec.get("scale", ls)))
			level |= (ls << 24) | (rs << 16)
		atk = -2 if spec.get("atk") == "?" else int(spec.get("atk", 0))
		if ctype & consts["TYPE_LINK"]:
			markers = spec.get("link_markers", [])
			names = {n: b for b, n in C.LINK_MARKERS}
			df = 0
			for m in markers:
				key = m.upper().replace("-", "").replace("_", "").replace(" ", "")
				key = {"TOPLEFT": "TL", "TOP": "T", "TOPRIGHT": "TR", "LEFT": "L", "RIGHT": "R",
				       "BOTTOMLEFT": "BL", "BOTTOM": "B", "BOTTOMRIGHT": "BR"}.get(key, key)
				if key not in names:
					sys.exit(f"unknown link marker {m}")
				df |= names[key]
		else:
			df = -2 if spec.get("def") == "?" else int(spec.get("def", 0))
		race = _names_to_bits(spec["race"], consts, "RACE_", "race")
		attr = _names_to_bits(spec["attribute"], consts, "ATTRIBUTE_", "attribute")
	strings = list(spec.get("strings", []))[:16]
	strings += [""] * (16 - len(strings))
	datas = (int(spec["id"]), ot, int(spec.get("alias", 0)), setcode, ctype, atk, df, level, race, attr,
	         int(spec.get("category", 0)))
	texts = (int(spec["id"]), spec["name"], spec.get("desc", ""), *strings)
	return datas, texts


def cmd_new(args):
	spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
	consts = C.parse_constants()
	datas, texts = build_row(spec, consts)
	cards = C.load_cards(args.cdb)
	if datas[0] in cards:
		print(f"note: passcode {datas[0]} already exists in: {', '.join(c.db for c in cards[datas[0]])}")
	print("datas:", datas)
	print("texts:", texts[:3], "+ strings:", [s for s in texts[3:] if s])
	if not args.write:
		print("dry run: pass --db PATH --write to insert/replace the row")
		return 0
	if not args.db:
		sys.exit("--write needs --db PATH")
	db = Path(args.db)
	con = sqlite3.connect(db)
	con.execute('CREATE TABLE IF NOT EXISTS "datas" ("id" INTEGER, "ot" INTEGER, "alias" INTEGER, '
	            '"setcode" INTEGER, "type" INTEGER, "atk" INTEGER, "def" INTEGER, "level" INTEGER, '
	            '"race" INTEGER, "attribute" INTEGER, "category" INTEGER, PRIMARY KEY("id"))')
	con.execute('CREATE TABLE IF NOT EXISTS "texts" ("id" INTEGER, "name" TEXT, "desc" TEXT, ' +
	            ", ".join(f'"str{i}" TEXT' for i in range(1, 17)) + ', PRIMARY KEY("id"))')
	con.execute("REPLACE INTO datas VALUES (?,?,?,?,?,?,?,?,?,?,?)", datas)
	con.execute("REPLACE INTO texts VALUES (" + ",".join("?" * 19) + ")", texts)
	con.commit()
	con.close()
	print(f"written to {db}")
	return 0


# ---------------------------------------------------------------- puzzles

PUZZLE_ZONES = {
	"hand": ("LOCATION_HAND", "POS_FACEDOWN"), "deck": ("LOCATION_DECK", "POS_FACEDOWN"),
	"extra": ("LOCATION_EXTRA", "POS_FACEDOWN"), "grave": ("LOCATION_GRAVE", "POS_FACEUP"),
	"banished": ("LOCATION_REMOVED", "POS_FACEUP"), "mzone": ("LOCATION_MZONE", "POS_FACEUP_ATTACK"),
	"szone": ("LOCATION_SZONE", "POS_FACEDOWN"), "fzone": ("LOCATION_FZONE", "POS_FACEUP"),
	"pzone": ("LOCATION_PZONE", "POS_FACEUP"),
}


def cmd_puzzle(args):
	"""Write an EDOPro puzzle (.lua) that sets up a board for manual testing."""
	cards = C.load_cards(args.cdb)
	lines = [f"--Test board: {args.title}", 'Debug.SetAIName("Test Opponent")',
	         "Debug.ReloadFieldBegin(DUEL_ATTACK_FIRST_TURN|DUEL_SIMPLE_AI,5)",
	         f"Debug.SetPlayerInfo(0,{args.lp},0,0)", f"Debug.SetPlayerInfo(1,{args.lp},0,0)"]
	seq: dict[tuple[int, str], int] = {}
	for spec in args.cards:
		player = 1 if spec.startswith("opp:") else 0
		spec = spec[4:] if player else spec
		zone, _, code = spec.partition(":")
		if zone not in PUZZLE_ZONES or not code:
			sys.exit(f"bad card spec {spec!r}; use [opp:]ZONE:PASSCODE with ZONE in {', '.join(PUZZLE_ZONES)}")
		hits = C.resolve_cards(code, cards)
		if not hits:
			sys.exit(f"{code}: not found")
		card = hits[0]
		loc, pos = PUZZLE_ZONES[zone]
		n = seq.get((player, zone), 0)
		seq[(player, zone)] = n + 1
		if zone == "pzone":
			loc, n = "LOCATION_PZONE", (0 if n == 0 else 1)
		lines.append(f"Debug.AddCard({card.id},{player},{player},{loc},{n},{pos}) --{card.name}")
	lines.append("Debug.ReloadFieldEnd()")
	if args.puzzle_rules:
		lines.append("aux.BeginPuzzle()")
	out = "\n".join(lines) + "\n"
	if args.output:
		Path(args.output).write_text(out, encoding="utf-8")
		print(f"wrote {args.output} (copy it to the EDOPro puzzles folder)")
	else:
		print(out)
	return 0


def main(argv=None):
	if hasattr(signal, "SIGPIPE"):
		signal.signal(signal.SIGPIPE, signal.SIG_DFL)
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("--cdb", action="append", default=[], help="extra .cdb file or folder (repeatable)")
	ap.add_argument("--scripts", action="append", default=[], help="extra script folder (repeatable)")
	sub = ap.add_subparsers(dest="cmd", required=True)

	p = sub.add_parser("show", help="decoded card data, strings and script paths")
	p.add_argument("cards", nargs="+")
	p.add_argument("--source", action="store_true", help="also print the script source")
	p.set_defaults(fn=cmd_show)

	p = sub.add_parser("search", help="regex search over card text/name")
	p.add_argument("regex")
	p.add_argument("--name", action="store_true", help="match the name only")
	p.add_argument("--text-only", action="store_true", help="match the effect text only")
	p.add_argument("--folder", action="append", help="only cards scripted in this folder (repeatable)")
	p.add_argument("--code", help="only cards whose script matches this regex")
	p.add_argument("--type", action="append", help="require TYPE_ bits, e.g. --type monster --type link")
	p.add_argument("--unscripted", action="store_true", help="only cards without a script")
	p.add_argument("--context", type=int, default=0, help="print N chars of context around the match")
	p.add_argument("--oldest", action="store_true", help="sort ascending by passcode")
	p.add_argument("--limit", type=int, default=20)
	p.set_defaults(fn=cmd_search)

	p = sub.add_parser("analogs", help="find scripted cards with similar clauses")
	p.add_argument("card", nargs="?")
	p.add_argument("--text", help="card text to analyse instead of a database card")
	p.add_argument("--top", type=int, default=5)
	p.add_argument("--folder", action="append", default=None,
	               help="folders to search (default: official, pre-release)")
	p.add_argument("--no-lines", dest="lines", action="store_false", help="skip locating comment lines")
	p.set_defaults(fn=cmd_analogs)

	p = sub.add_parser("archetype", help="SET_ constants by name or value")
	p.add_argument("query")
	p.set_defaults(fn=cmd_archetype)

	p = sub.add_parser("new", help="create a database row from a JSON spec")
	p.add_argument("spec")
	p.add_argument("--db", help="target .cdb (created if missing)")
	p.add_argument("--write", action="store_true")
	p.set_defaults(fn=cmd_new)

	p = sub.add_parser("puzzle", help="write a puzzle file that sets up a test board")
	p.add_argument("cards", nargs="+", help="[opp:]ZONE:PASSCODE|NAME, e.g. hand:101402082 opp:mzone:89631139")
	p.add_argument("--title", default="card test")
	p.add_argument("--lp", type=int, default=8000)
	p.add_argument("--puzzle-rules", action="store_true", help="append aux.BeginPuzzle() (lose at end of turn)")
	p.add_argument("-o", "--output")
	p.set_defaults(fn=cmd_puzzle)

	args = ap.parse_args(argv)
	if args.cmd == "analogs":
		if not args.card and not args.text:
			ap.error("analogs needs a card or --text")
		args.folder = args.folder or ["official", "pre-release"]
	return args.fn(args)


if __name__ == "__main__":
	sys.exit(main())
