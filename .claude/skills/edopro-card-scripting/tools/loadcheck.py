#!/usr/bin/env python3
"""Load-test card scripts in the real EDOPro core, the same way the CardScripts CI does.

The CI job downloads ProjectIgnis/ScriptChecker and a prebuilt libocgcore.so, loads
constant.lua and utility.lua, then loads every cX.lua and runs its initial_effect.
This tool reproduces that locally:

  loadcheck.py setup            build libocgcore.so from ygopro-core and fetch ScriptChecker
  loadcheck.py run FILE...      check the given scripts (fast: only these files are loaded)
  loadcheck.py run --full       check every script in the repository (about 10 s)
  loadcheck.py symbols          dump the runtime Lua globals (used by lint.py) to the cache

What it catches: Lua syntax errors, runtime errors inside initial_effect (nil functions,
misspelled constants passed to Set* calls, wrong parameter types), a missing initial_effect.
What it cannot catch: errors inside condition/cost/target/operation functions, which only
run during a duel. Use lint.py for those and test in the client.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

CHECKER_URL = "https://github.com/ProjectIgnis/ScriptChecker/releases/latest/download/ScriptChecker-linux.zip"
LUA_REPO = "https://github.com/lua/lua"
LUA_DEFAULT_PIN = "6e22fedb74cf0c9b6656e9fce8b7331db847c605"  # submodule pin of ygopro-core (Lua 5.4.8), 2026-06
CACHE = C.CACHE_DIR
CHECKER = CACHE / "script_syntax_check"
LIBCORE = CACHE / "libocgcore.so"
SYMBOLS = CACHE / "symbols.tsv"
LUA_EXCLUDE = {"lbitlib", "lcorolib", "ldblib", "linit", "loadlib", "loslib", "ltests", "lua", "luac",
               "lutf8lib", "onelua"}


def log(msg):
	print(f"[loadcheck] {msg}", file=sys.stderr)


def run(cmd, **kw):
	return subprocess.run(cmd, check=True, **kw)


def lua_source_dir() -> Path:
	in_repo = C.CORE_DIR / "lua" / "src"
	if (in_repo / "lapi.c").is_file():
		return in_repo
	cached = CACHE / "lua-src"
	if (cached / "lapi.c").is_file():
		return cached
	sha = None
	try:
		out = subprocess.run(["git", "-C", str(C.CORE_DIR), "ls-tree", "HEAD", "lua/src"],
		                     capture_output=True, text=True, check=True).stdout.split()
		sha = out[2] if len(out) >= 3 else None
	except Exception:
		pass
	sha = sha or LUA_DEFAULT_PIN
	log(f"fetching Lua sources ({sha}) into {cached}")
	cached.mkdir(parents=True, exist_ok=True)
	run(["git", "init", "-q", str(cached)])
	run(["git", "-C", str(cached), "fetch", "-q", "--depth", "1", LUA_REPO, sha])
	run(["git", "-C", str(cached), "checkout", "-q", "FETCH_HEAD"])
	return cached


def build_core(force=False):
	if LIBCORE.is_file() and not force:
		return
	if not (C.CORE_DIR / "ocgapi.cpp").is_file():
		sys.exit(f"ygopro-core not found at {C.CORE_DIR} (set EDOPRO_CORE)")
	for tool in ("g++",):
		if not shutil.which(tool):
			sys.exit(f"{tool} is required to build libocgcore.so")
	lua_src = lua_source_dir()
	obj = CACHE / "obj"
	obj.mkdir(parents=True, exist_ok=True)
	conf = C.CORE_DIR / "lua" / "luaconf-customize.h"
	jobs = []
	for f in sorted(lua_src.glob("*.c")):
		if f.stem in LUA_EXCLUDE:
			continue
		cmd = ["g++", "-x", "c++", "-O2", "-fPIC", "-I", str(lua_src)]
		if conf.is_file():
			cmd += ["-include", str(conf)]
		jobs.append(cmd + ["-c", str(f), "-o", str(obj / f"lua_{f.stem}.o")])
	for f in sorted(list(C.CORE_DIR.glob("*.cpp")) + list(C.CORE_DIR.glob("RNG/*.cpp"))):
		jobs.append(["g++", "-std=c++17", "-O2", "-fPIC", "-fno-rtti", "-DOCGCORE_EXPORT_FUNCTIONS",
		             "-fvisibility=hidden", "-Wno-unused-parameter", "-I", str(lua_src), "-c", str(f),
		             "-o", str(obj / f"core_{f.stem}.o")])
	log(f"compiling {len(jobs)} files from {C.CORE_DIR} ...")
	with cf.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
		results = list(ex.map(lambda c: subprocess.run(c, capture_output=True, text=True), jobs))
	failed = [r for r in results if r.returncode != 0]
	if failed:
		sys.exit("compile failed:\n" + failed[0].stderr[-3000:])
	run(["g++", "-shared", "-o", str(LIBCORE), *map(str, sorted(obj.glob("*.o"))),
	     "-static-libgcc", "-static-libstdc++", "-Wl,--no-undefined"])
	log(f"built {LIBCORE}")


def fetch_checker(force=False):
	if CHECKER.is_file() and not force:
		return
	CACHE.mkdir(parents=True, exist_ok=True)
	zpath = CACHE / "ScriptChecker.zip"
	log(f"downloading {CHECKER_URL}")
	try:
		with urllib.request.urlopen(CHECKER_URL, timeout=60) as r, open(zpath, "wb") as f:
			shutil.copyfileobj(r, f)
	except Exception:
		# urllib may not honour the proxy CA in some sandboxes; fall back to curl
		run(["curl", "-sSfL", "--retry", "3", "-o", str(zpath), CHECKER_URL])
	with zipfile.ZipFile(zpath) as z:
		z.extractall(CACHE)
	CHECKER.chmod(0o755)
	log(f"installed {CHECKER}")


def setup(force=False):
	CACHE.mkdir(parents=True, exist_ok=True)
	build_core(force)
	fetch_checker(force)


def make_tree(files: list[Path]) -> Path:
	tmp = Path(tempfile.mkdtemp(prefix="edopro-check-"))
	for f in C.SCRIPTS_ROOT.glob("*.lua"):
		(tmp / f.name).symlink_to(f)
	unofficial = C.SCRIPTS_ROOT / "unofficial" / "proc_unofficial.lua"
	if unofficial.is_file():
		(tmp / unofficial.name).symlink_to(unofficial)
	sub = tmp / "check"
	sub.mkdir()
	for f in files:
		shutil.copy(f, sub / f.name)
	return tmp


def run_checker(root: Path) -> tuple[int, str]:
	p = subprocess.run([str(CHECKER), str(root)], cwd=CACHE, capture_output=True, text=True)
	return p.returncode, p.stdout + p.stderr


def filter_output(out: str) -> list[str]:
	keep = []
	for line in out.splitlines():
		if line.startswith(("Passed script folder", "Found script folder")):
			continue
		if "proc_unofficial.lua, while parsing c0.lua" in line:
			continue
		keep.append(line)
	return keep


def nested_folders_with_files(root: Path) -> list[Path]:
	"""Non-hidden folders two or more levels deep that contain files.

	ScriptChecker (the CI checker) fails to open the root proc_*.lua libraries when such a
	folder exists, so the CI job goes red even though every script is fine.
	"""
	bad = []
	for sub in root.iterdir():
		if not sub.is_dir() or sub.name.startswith("."):
			continue
		for d in sub.rglob("*"):
			if d.is_dir() and not any(part.startswith(".") for part in d.relative_to(root).parts):
				if any(f.is_file() for f in d.iterdir()):
					bad.append(d)
	return bad


def cmd_run(args):
	setup()
	nested = nested_folders_with_files(C.SCRIPTS_ROOT)
	for d in nested:
		log(f"warning: nested folder with files breaks the CI ScriptChecker: {d.relative_to(C.SCRIPTS_ROOT)}")
	if args.full:
		code, out = run_checker(C.SCRIPTS_ROOT)
		lines = filter_output(out)
	else:
		files = [Path(f).resolve() for f in args.files]
		if not files:
			sys.exit("give script paths, or --full")
		for f in files:
			if not f.is_file():
				sys.exit(f"not found: {f}")
			stem = f.stem
			if not (stem.startswith("c") and stem[1:].isdigit()):
				log(f"warning: {f.name} is not named cPASSCODE.lua; the checker will skip it")
			elif len(stem) - 1 <= 3:
				log(f"warning: {f.name} has a passcode of 3 digits or fewer; the checker skips those")
		tree = make_tree(files)
		try:
			code, out = run_checker(tree)
		finally:
			shutil.rmtree(tree, ignore_errors=True)
		lines = filter_output(out)
	for line in lines:
		print(line)
	if code == 0 and not any(l.startswith(("Error", "Failed")) for l in lines):
		print("OK: scripts loaded and initial_effect ran without errors")
		return 0
	print("FAILED")
	return 1


DUMP_SCRIPT = r'''local s,id=GetID()
function s.initial_effect(c)
	local out={}
	for k,v in pairs(_G) do
		if type(k)=="string" then
			local tv=type(v)
			if tv=="table" and k~="_G" and k~="package" then
				for k2,v2 in pairs(v) do
					if type(k2)=="string" then out[#out+1]=k.."."..k2.."\t"..type(v2) end
				end
				out[#out+1]=k.."\ttable"
			elseif tv=="number" then
				out[#out+1]=k.."\tnumber\t"..string.format("0x%x",v)
			else
				out[#out+1]=k.."\t"..tv
			end
		end
	end
	table.sort(out)
	error("DUMPSTART\n"..table.concat(out,"\n").."\nDUMPEND")
end
'''


def cmd_symbols(args):
	setup()
	tmp = Path(tempfile.mkdtemp(prefix="edopro-dump-"))
	try:
		f = tmp / "c999999999.lua"
		f.write_text(DUMP_SCRIPT, encoding="utf-8")
		tree = make_tree([f])
		_, out = run_checker(tree)
		shutil.rmtree(tree, ignore_errors=True)
	finally:
		shutil.rmtree(tmp, ignore_errors=True)
	if "DUMPSTART" not in out:
		sys.exit("symbol dump failed:\n" + out[-2000:])
	body = out.split("DUMPSTART\n", 1)[1].split("\nDUMPEND", 1)[0]
	SYMBOLS.write_text(body + "\n", encoding="utf-8")
	print(f"wrote {len(body.splitlines())} symbols to {SYMBOLS}")
	return 0


def main(argv=None):
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	sub = ap.add_subparsers(dest="cmd", required=True)
	p = sub.add_parser("setup")
	p.add_argument("--force", action="store_true", help="rebuild the core and re-download the checker")
	p.set_defaults(fn=lambda a: setup(a.force) or 0)
	p = sub.add_parser("run")
	p.add_argument("files", nargs="*")
	p.add_argument("--full", action="store_true", help="check the whole repository")
	p.set_defaults(fn=cmd_run)
	p = sub.add_parser("symbols")
	p.set_defaults(fn=cmd_symbols)
	args = ap.parse_args(argv)
	return args.fn(args)


if __name__ == "__main__":
	sys.exit(main())
