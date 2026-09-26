#!/usr/bin/env python3
"""Random exploration of custom cards in ygopro-core, the engine EDOPro embeds.

For every selected card and seed: build a board around the card's archetype, play several
turns with a seeded random policy for both players, and report
  * Lua errors, invalid prompts, engine loops and crashes (each duel runs in its own process),
  * rule violations found by duelcheck.py (usage limits, summon/activation locks),
  * prompt strings (aux.Stringid) missing from the database,
  * activated effects that no duel reached (write scenario tests for those).

  explore.py                                  # every scripted custom card, 16 seeds
  explore.py --cards 270000301,270000308 --seeds 48
  explore.py --block 2700003 --out lavoisier.json
  explore.py --report lavoisier.json          # print the report of a saved run
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import random
import re
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duelcheck  # noqa: E402
from duelsim import (DB, EXTRA_TYPES, MSG, POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK, TYPE_FIELD,  # noqa: E402
                     TYPE_MONSTER, TYPE_PENDULUM, TYPE_TOKEN, Duel, DuelError, RandomPolicy, find_script)

TYPE_SKILL = 0x8000000
CUSTOM_SETCODE_RANGE = range(0xE00, 0xF00)  # low 12 bits of the custom archetype setcodes

# Cards added to the exploration deck of a custom card whose support is not found through its
# setcodes (project data: official cards that the custom card names or needs).
PROJECT_SUPPORT = {
	270000099: [68468459, 44146295, 41373230, 70534340, 87746184, 44362883, 24094653],  # Albaz, the Fallen
	270000113: [5818798, 69247929, 76812113],  # Party, Assemble!: a Beast, Beast-Warrior, Winged Beast
}

OPP_DECK = [55144522, 5318639, 12580477, 53129443, 83764718, 40640057, 44095762, 4206964, 89631139, 46986414] * 2
OPP_HAND_INTERACTIVE = [97268402, 14558127, 10045474, 5318639, 40605147]  # Veiler, Ash, Impermanence, MST, Solemn Strike
OPP_HAND_PASSIVE = [89631139, 46986414, 40640057]
VARIANTS = ["hand", "field", "grave", "removed"]

# ---------------------------------------------------------------- pools
def testable_custom() -> list[int]:
	out = []
	for code in sorted(DB.custom):
		t = DB.type(code)
		if t & (TYPE_TOKEN | TYPE_SKILL) or not find_script(f"c{code}.lua"):
			continue
		out.append(code)
	return out

def is_extra(code: int) -> bool:
	return bool(DB.type(code) & EXTRA_TYPES)

_official_cache: dict[int, list[int]] = {}
def official_with_setcode(setcode: int) -> list[int]:
	if setcode not in _official_cache:
		codes = DB.codes_with_setcode(setcode)
		_official_cache[setcode] = [c for c in codes if c not in DB.custom and not DB.type(c) & TYPE_TOKEN
		                            and (find_script(f"c{c}.lua") or DB.type(c) & 0x10)]
	return _official_cache[setcode]

def pool_for(code: int, custom: list[int]) -> list[int]:
	block = [c for c in custom if c // 100 == code // 100]
	counts: dict[int, int] = defaultdict(int)
	for c in block:
		for sc in DB.setcodes(c):
			if (sc & 0xFFF) not in CUSTOM_SETCODE_RANGE:
				counts[sc] += 1
	pool = set(block)
	for sc, n in counts.items():
		if n >= 2:
			pool.update(official_with_setcode(sc))
	for c in block:
		pool.update(PROJECT_SUPPORT.get(c, []))
	return sorted(c for c in pool if DB.row(c) and not DB.type(c) & TYPE_TOKEN)

# ---------------------------------------------------------------- one duel
def place_target(d: Duel, code: int, variant: str, rng: random.Random):
	t = DB.type(code)
	if variant == "hand":
		d.add(code, 0, "extra" if is_extra(code) else "hand")
	elif variant == "field":
		if t & TYPE_MONSTER and not (t & TYPE_PENDULUM and rng.random() < 0.5):
			d.add(code, 0, "mzone", seq=2, pos=POS_FACEUP_ATTACK)
		elif t & TYPE_PENDULUM:
			d.add(code, 0, "pzone", seq=0, pos=POS_FACEUP_ATTACK)
		elif t & TYPE_FIELD:
			d.add(code, 0, "fzone", pos=POS_FACEUP_ATTACK)
		else:
			d.add(code, 0, "szone", seq=2, pos=POS_FACEDOWN_DEFENSE)
	elif variant == "grave":
		d.add(code, 0, "grave")
	elif variant == "removed":
		d.add(code, 0, "removed")

def run_one(target: int, seed: int, variant: str, interactive: bool, pool: list[int],
            max_prompts=450, max_turns=6) -> dict:
	rng = random.Random(seed * 7919 + target)
	main = [c for c in pool if not is_extra(c)]
	extra = [c for c in pool if is_extra(c)]
	d = Duel(seed=seed + target % 100000)
	place_target(d, target, variant, rng)
	if main:
		for c in rng.sample(main, min(4, len(main))):
			d.add(c, 0, "hand")
		deck = main * 2 + ([target] * 2 if not is_extra(target) else [])
		rng.shuffle(deck)
		for c in deck[:40]:
			d.add(c, 0, "deck")
		mons = [c for c in main if DB.type(c) & TYPE_MONSTER]
		for i, c in enumerate(rng.sample(mons, min(2, len(mons)))):
			d.add(c, 0, "mzone", seq=i, pos=POS_FACEUP_ATTACK)
		for c in rng.sample(main, min(3, len(main))):
			d.add(c, 0, "grave")
		for c in rng.sample(main, min(2, len(main))):
			d.add(c, 0, "removed")
	for c in extra:
		d.add(c, 0, "extra")
	if is_extra(target) and variant != "hand":
		d.add(target, 0, "extra")
	opp = OPP_DECK[:]
	rng.shuffle(opp)
	for c in opp:
		d.add(c, 1, "deck")
	for c in (OPP_HAND_INTERACTIVE if interactive else OPP_HAND_PASSIVE):
		d.add(c, 1, "hand")
	d.add(89631139, 1, "mzone", seq=0)
	d.add(46986414, 1, "mzone", seq=1)
	d.add(44095762, 1, "szone", seq=0, pos=POS_FACEDOWN_DEFENSE)
	d.add(40640057, 1, "grave")
	d.lua(duelcheck.OBSERVER, "observer.lua")
	d.start()
	pol = RandomPolicy(seed, passive_players=() if interactive else (1,))
	def until(du, m):
		return sum(1 for x in du.messages if x.type == MSG["NEW_TURN"]) > max_turns
	exc = None
	try:
		n = d.run(pol, max_prompts=max_prompts, until=until)
	except DuelError as e:
		exc = str(e); n = len(d.trace)
	except Exception:
		exc = "python: " + traceback.format_exc(limit=3); n = len(d.trace)
	custom = DB.custom
	chained, descs = [], set()
	for m in d.messages:
		dd = m.data
		if m.type == MSG["CHAINING"]:
			owner = dd["desc"] >> 20
			if owner in custom:
				chained.append([owner, dd["desc"] & 0xFFFFF])
			continue
		if "desc" in dd:
			descs.add(dd["desc"])
		if m.name == "SELECT_OPTION":
			descs.update(dd["options"])
		for k in ("activate", "chains"):
			for x in dd.get(k, []) or []:
				descs.add(x["desc"])
		if m.name == "HINT" and dd.get("htype") in (3, 4):
			descs.add(dd.get("hdata", 0))
	res = dict(target=target, seed=seed, variant=variant, interactive=interactive, prompts=n,
	           turns=sum(1 for x in d.messages if x.type == MSG["NEW_TURN"]), errors=d.errors,
	           retries=d.retries, exc=exc, chained=chained, ended=d.ended,
	           violations=duelcheck.check(d.script_log, custom),
	           descs=sorted(x for x in descs if (x >> 20) in custom),
	           missing=sorted(x for x in d.missing_scripts if x[1:-4].isdigit() and int(x[1:-4]) in custom),
	           trace=d.trace[-60:] if (d.errors or d.retries or exc) else [])
	d.close()
	return res

# ---------------------------------------------------------------- process pool (crash isolation)
def _worker(args, conn):
	try:
		conn.send(run_one(*args))
	except Exception:
		conn.send(dict(target=args[0], seed=args[1], variant=args[2], interactive=args[3],
		               exc="worker: " + traceback.format_exc(limit=4), errors=[], retries=0, chained=[]))
	conn.close()

def run_all(tasks, jobs=4, timeout=120) -> list[dict]:
	ctx = mp.get_context("fork")
	results, running, queue = [], [], list(tasks)
	def failed(t, why):
		return dict(target=t[0], seed=t[1], variant=t[2], interactive=t[3], exc=why, errors=[], retries=0, chained=[])
	while queue or running:
		while queue and len(running) < jobs:
			t = queue.pop(0)
			a, b = ctx.Pipe(duplex=False)
			p = ctx.Process(target=_worker, args=(t, b))
			p.start(); b.close()
			running.append((p, a, t, time.time()))
		for item in running[:]:
			p, a, t, t0 = item
			if a.poll():
				try:
					results.append(a.recv())
				except EOFError:
					results.append(failed(t, f"process died (exit code {p.exitcode})"))
				p.join(); running.remove(item)
			elif not p.is_alive():
				p.join()
				results.append(a.recv() if a.poll() else failed(t, f"process died (exit code {p.exitcode})"))
				running.remove(item)
			elif time.time() - t0 > timeout:
				p.kill(); p.join(); running.remove(item)
				results.append(failed(t, "timeout"))
		time.sleep(0.01)
	return results

# ---------------------------------------------------------------- report
def activated_descs(code: int) -> set[int]:
	"""String indices of activated effects (ACTIVATE/IGNITION/QUICK/TRIGGER, incl. granted ones)."""
	path = find_script(f"c{code}.lua")
	if not path:
		return set()
	src = path.read_text(encoding="utf-8", errors="replace")
	out = set()
	for m in re.finditer(r"local (e\w+)=Effect\.CreateEffect\(c\)(.*?)(?=local e\w+=Effect\.CreateEffect|\nend\n)", src, re.S):
		var, body = m.group(1), m.group(2)
		dsc = re.search(var + r":SetDescription\(aux\.Stringid\(id,(\d+)\)\)", body)
		typ = re.search(var + r":SetType\(([^)]*)\)", body)
		if dsc and typ and re.search(r"ACTIVATE|IGNITION|QUICK|TRIGGER", typ.group(1)):
			out.add(int(dsc.group(1)))
	return out

def strings_of(code: int) -> list[str] | None:
	for con in DB.cons:
		r = con.execute("select " + ",".join(f"str{i}" for i in range(1, 17)) + " from texts where id=?", (code,)).fetchone()
		if r:
			return [x or "" for x in r]
	return None

def report(res: list[dict]) -> int:
	by = defaultdict(list)
	covered = defaultdict(set)
	for r in res:
		by[r["target"]].append(r)
		for code, idx in r.get("chained", []):
			covered[code].add(idx)
	issues = 0
	print("== errors, invalid prompts, loops, crashes")
	for code in sorted(by):
		for r in by[code]:
			if r.get("errors") or r.get("retries") or r.get("exc"):
				issues += 1
				print(f"{code} {DB.name(code)} seed={r['seed']} {r['variant']} interactive={r['interactive']}"
				      f" retries={r.get('retries')} exc={(r.get('exc') or '')[:200]}")
				for e in r.get("errors", [])[:4]:
					print("   ERR", e[:400])
	print(f"-- {issues} duel(s) with problems out of {len(res)}")
	print("== rule violations")
	viol = defaultdict(list)
	for r in res:
		for v in r.get("violations", []):
			viol[v].append((r["target"], r["seed"], r["variant"], r["interactive"]))
	for v, runs in sorted(viol.items()):
		print(f"{v}   [{len(runs)} duel(s), e.g. target/seed/variant/interactive {runs[0]}]")
	print(f"-- {len(viol)} distinct violation(s)")
	print("== prompt strings missing from the database")
	seen = set()
	for r in res:
		seen.update(r.get("descs", []))
	nmiss = 0
	for dsc in sorted(seen):
		owner, idx = dsc >> 20, dsc & 0xFFFFF
		strs = strings_of(owner)
		if strs is None or idx >= 16 or not strs[idx].strip():
			nmiss += 1
			print(f"{owner} {DB.name(owner)}: str{idx + 1} is empty (aux.Stringid(id,{idx}))")
	print(f"-- {nmiss} missing string(s) among {len(seen)} used")
	print("== activated effects never reached (cover them with scenario tests)")
	gaps = 0
	for code in sorted(by):
		miss = sorted(activated_descs(code) - covered.get(code, set()))
		if miss:
			gaps += len(miss)
			print(f"{code} {DB.name(code)}: str index {miss}")
	print(f"-- {gaps} effect(s) not reached")
	return issues + len(viol) + nmiss

def main():
	ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
	ap.add_argument("--cards", default="", help="comma-separated passcodes (default: every scripted custom card)")
	ap.add_argument("--block", type=int, action="append", default=[], help="passcode // 100 of an archetype block")
	ap.add_argument("--seeds", type=int, default=16)
	ap.add_argument("--jobs", type=int, default=4)
	ap.add_argument("--turns", type=int, default=6)
	ap.add_argument("--out", default="", help="save the raw results as JSON")
	ap.add_argument("--report", default="", help="only print the report of a saved JSON file")
	a = ap.parse_args()
	if a.report:
		sys.exit(1 if report(json.load(open(a.report))) else 0)
	custom = testable_custom()
	cards = [int(x) for x in a.cards.split(",") if x] or [c for c in custom if not a.block or c // 100 in a.block]
	pools = {c: pool_for(c, custom) for c in cards}
	tasks = [(c, s, VARIANTS[s % len(VARIANTS)], s % 2 == 0, pools[c], 450, a.turns)
	         for c in cards for s in range(a.seeds)]
	t0 = time.time()
	res = run_all(tasks, jobs=a.jobs)
	print(f"{len(res)} duels for {len(cards)} card(s) in {time.time() - t0:.0f}s")
	if a.out:
		json.dump(res, open(a.out, "w"))
	sys.exit(1 if report(res) else 0)

if __name__ == "__main__":
	main()
