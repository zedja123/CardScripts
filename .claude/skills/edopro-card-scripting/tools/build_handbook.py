#!/usr/bin/env python3
"""Render docs/*.md into one self-contained HTML page (the published handbook).

  build_handbook.py -o handbook.html

Requires the `markdown` package (pip install markdown); everything else is inline.
Chapter links become in-page anchors; other repository paths link to GitHub.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

try:
	import markdown
except ImportError:
	sys.exit("build_handbook.py needs the markdown package: pip install markdown")

DOCS = C.SCRIPTS_ROOT / "docs"
REPO_URL = "https://github.com/zedja123/CardScripts/blob/{branch}/{path}"
HLJS = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0"

CHAPTERS = [
	("overview", "README.md", "Overview"),
	("ch01", "01-workflow.md", "01"),
	("ch02", "02-psct-to-lua.md", "02"),
	("ch03", "03-script-conventions.md", "03"),
	("ch04", "04-cookbook.md", "04"),
	("ch05", "05-api-reference.md", "05"),
	("ch06", "06-card-database.md", "06"),
	("ch07", "07-engine-notes.md", "07"),
	("ch08", "08-testing-and-review.md", "08"),
	("ch09", "09-sources.md", "09"),
]

ANATOMY = """<figure class="anatomy" aria-label="Anatomy of an activated effect">
<div class="anatomy-strip">
<span class="seg seg-cond"><b>If this card is sent to the GY</b><i>activation condition</i></span><span class="punct">:</span>
<span class="seg seg-cost"><b>You can target 1 Spell in your GY</b><i>cost / targets (on activation)</i></span><span class="punct">;</span>
<span class="seg seg-res"><b>add it to your hand.</b><i>resolution</i></span>
</div>
<figcaption>Everything before the colon decides <em>when</em> (<code>SetType</code>, <code>SetCode</code>, <code>SetCondition</code>);
between colon and semicolon happens on activation (<code>SetCost</code>, target selection in <code>SetTarget</code>);
after the semicolon happens on resolution (<code>SetOperation</code>).</figcaption>
</figure>"""


def slug(text: str) -> str:
	s = re.sub(r"<[^>]+>", "", text)
	s = html.unescape(s).lower()
	s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
	return s or "section"


def convert(md_text: str) -> tuple[str, str]:
	lines = md_text.split("\n")
	title = ""
	if lines and lines[0].startswith("# "):
		title = lines[0][2:].strip()
		lines = lines[1:]
	body = markdown.markdown("\n".join(lines), extensions=["tables", "fenced_code", "sane_lists"],
	                         output_format="html")
	return title, body


def rewrite_links(body: str, file_to_id: dict[str, str], branch: str) -> str:
	def fix(m):
		href = m.group(1)
		if href.startswith(("http://", "https://")):
			return f'href="{href}" target="_blank" rel="noopener"'
		if href.startswith("#"):
			return f'href="{href}"'
		path, _, frag = href.partition("#")
		name = Path(path).name
		if name in file_to_id:
			return f'href="#{frag or file_to_id[name]}"'
		clean = re.sub(r"^(\./|\.\./)+", "", path)
		if not clean.startswith((".claude", "docs", "ZedjaCustomCards")):
			clean = f".claude/skills/edopro-card-scripting/{clean}" if clean.startswith(("tools", "templates")) else clean
		url = REPO_URL.format(branch=branch, path=clean)
		return f'href="{url}" target="_blank" rel="noopener"'
	return re.sub(r'href="([^"]+)"', fix, body)


def build(branch: str) -> str:
	file_to_id = {f: cid for cid, f, _ in CHAPTERS}
	sections, nav = [], []
	for cid, fname, label in CHAPTERS:
		title, body = convert((DOCS / fname).read_text(encoding="utf-8"))
		if cid == "overview":
			title = "Overview"
		else:
			title = re.sub(r"^\d+\s*·\s*", "", title)
		body = rewrite_links(body, file_to_id, branch)
		# shift heading levels: ## -> h3, ### -> h4 (the chapter title is the h2)
		for lvl in (4, 3, 2):
			body = re.sub(rf"<(/?)h{lvl}>", rf"<\1h{lvl + 1}>", body)
		used = set()
		subs = []

		def add_id(m):
			text = m.group(2)
			base = f"{cid}-{slug(text)}"
			hid, n = base, 2
			while hid in used:
				hid, n = f"{base}-{n}", n + 1
			used.add(hid)
			if m.group(1) == "3":
				subs.append((hid, re.sub(r"<[^>]+>", "", text)))
			return f'<h{m.group(1)} id="{hid}">{text}</h{m.group(1)}>'
		body = re.sub(r"<h([34])>(.*?)</h\1>", add_id, body)
		body = re.sub(r"<table>", '<div class="table-wrap"><table>', body)
		body = body.replace("</table>", "</table></div>")
		body = body.replace("<pre><code>", '<pre><code class="nohighlight">')
		body = re.sub(r'<pre><code class="language-(\w+)">', r'<pre><code class="language-\1">', body)
		if cid == "ch02":
			body = re.sub(r'<pre><code class="nohighlight">\[activation condition / timing\].*?</code></pre>',
			              lambda _: ANATOMY, body, count=1, flags=re.S)
		eyebrow = "Start here" if cid == "overview" else f"Chapter {label}"
		sections.append(f'<section class="chapter" id="{cid}" data-title="{html.escape(title)}">'
		                f'<p class="eyebrow">{eyebrow}</p><h2>{html.escape(title)}</h2>{body}</section>')
		sub_html = "".join(f'<li><a href="#{hid}" data-sub>{html.escape(t)}</a></li>' for hid, t in subs)
		num = "" if cid == "overview" else f'<span class="num">{label}</span>'
		nav.append(f'<li class="nav-ch" data-ch="{cid}"><a href="#{cid}" class="nav-ch-link">{num}'
		           f'<span>{html.escape(title)}</span></a><ol class="nav-sub">{sub_html}</ol></li>')
	return PAGE.replace("%%NAV%%", "".join(nav)).replace("%%SECTIONS%%", "\n".join(sections)) \
		.replace("%%HLJS%%", HLJS).replace("%%PR%%", "https://github.com/zedja123/CardScripts/pull/1")


PAGE = r"""<title>EDOPro Scripting Handbook</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&family=Saira+Semi+Condensed:wght@500;600;700&display=swap">
<style>
:root{
  --bg:#f5f7f7; --surface:#ffffff; --ink:#1a2326; --muted:#5b6b70; --line:#d9e2e3; --line-strong:#c3d0d2;
  --accent:#13796f; --accent-soft:#e0f0ee; --effect:#b8621b; --effect-soft:#f8ecdf; --trap:#a33a78; --trap-soft:#f6e6ef;
  --code-bg:#eef3f3; --code-ink:#1f2b2e; --mark:#fff3b0;
  --hl-kw:#a33a78; --hl-str:#13796f; --hl-num:#b8621b; --hl-com:#7a8a8e; --hl-fn:#2c5d8a; --hl-const:#8a5a00;
  --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --display:"Saira Semi Condensed","Arial Narrow",system-ui,sans-serif;
  --side:272px;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme:dark;
    --bg:#0e1416; --surface:#151d20; --ink:#e2ebec; --muted:#93a4a8; --line:#26343a; --line-strong:#33454c;
    --accent:#3fbfae; --accent-soft:#12302d; --effect:#e3a15a; --effect-soft:#33240f; --trap:#e07ab5; --trap-soft:#3a1a2c;
    --code-bg:#11191c; --code-ink:#d6e2e3; --mark:#5c4d0e;
    --hl-kw:#e07ab5; --hl-str:#3fbfae; --hl-num:#e3a15a; --hl-com:#7d9095; --hl-fn:#8ab8e6; --hl-const:#e0c070;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --bg:#0e1416; --surface:#151d20; --ink:#e2ebec; --muted:#93a4a8; --line:#26343a; --line-strong:#33454c;
  --accent:#3fbfae; --accent-soft:#12302d; --effect:#e3a15a; --effect-soft:#33240f; --trap:#e07ab5; --trap-soft:#3a1a2c;
  --code-bg:#11191c; --code-ink:#d6e2e3; --mark:#5c4d0e;
  --hl-kw:#e07ab5; --hl-str:#3fbfae; --hl-num:#e3a15a; --hl-com:#7d9095; --hl-fn:#8ab8e6; --hl-const:#e0c070;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion: reduce){html{scroll-behavior:auto}}
body{background:var(--bg);color:var(--ink);font:15px/1.65 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-underline-offset:2px}
a:focus-visible,button:focus-visible,input:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
code{font-family:var(--mono);font-size:.86em;background:var(--code-bg);color:var(--code-ink);padding:.1em .35em;border-radius:4px;overflow-wrap:anywhere}
pre{margin:0 0 1.2rem;background:var(--code-bg);border:1px solid var(--line);border-radius:8px;overflow-x:auto;font-size:13px;line-height:1.55}
pre code{display:block;padding:14px 16px;background:none;border-radius:0;font-size:1em;overflow-wrap:normal;white-space:pre;tab-size:4}

/* layout */
.shell{display:grid;grid-template-columns:var(--side) minmax(0,1fr);min-height:100%}
.side{position:sticky;top:env(safe-area-inset-top,0px);height:100vh;overflow-y:auto;border-right:1px solid var(--line);background:var(--surface);padding:22px 16px 40px}
.brand{font:700 20px/1.1 var(--display);letter-spacing:.01em;margin:0 0 4px}
.brand small{display:block;font:500 12px/1.4 var(--sans);color:var(--muted);letter-spacing:0;margin-top:6px}
.filter{margin:16px 0 14px;position:relative}
.filter input{width:100%;font:14px var(--sans);color:var(--ink);background:var(--bg);border:1px solid var(--line-strong);border-radius:6px;padding:8px 10px}
.filter input::placeholder{color:var(--muted)}
.nav{list-style:none;margin:0;padding:0;display:grid;gap:2px}
.nav-ch-link{display:flex;gap:10px;align-items:baseline;padding:6px 8px;border-radius:6px;color:var(--ink);text-decoration:none;font-weight:500}
.nav-ch-link:hover{background:var(--accent-soft)}
.nav-ch-link .num{font:600 12px var(--mono);color:var(--muted);min-width:1.6em}
.nav-ch.active>.nav-ch-link{background:var(--accent-soft);color:var(--accent)}
.nav-ch.active>.nav-ch-link .num{color:var(--accent)}
.nav-sub{list-style:none;margin:2px 0 8px;padding:0 0 0 34px;display:none}
.nav-ch.active .nav-sub,.side.filtering .nav-sub{display:grid;gap:1px}
.nav-sub a{display:block;padding:3px 6px;border-radius:4px;color:var(--muted);text-decoration:none;font-size:13px;line-height:1.35}
.nav-sub a:hover{color:var(--ink);background:var(--bg)}
.nav-sub a.current{color:var(--accent);font-weight:500}
.side.filtering .nav-ch.nomatch,.side.filtering .nav-sub li.nomatch{display:none}
.nav-empty{color:var(--muted);font-size:13px;padding:6px 8px}
.side-foot{margin-top:18px;padding-top:14px;border-top:1px solid var(--line);font-size:12px;color:var(--muted);display:grid;gap:6px}

.main{padding-inline:clamp(16px,4vw,56px);padding-block:32px 96px;min-width:0}
.content{max-width:820px}
.topbar{display:none}

/* hero */
.hero{padding-block:8px 28px;border-bottom:1px solid var(--line);margin-bottom:8px}
.hero h1{font:700 clamp(30px,5vw,44px)/1.05 var(--display);letter-spacing:.005em;margin:0 0 12px;text-wrap:balance}
.hero p.lede{font-size:17px;color:var(--muted);max-width:62ch;margin:0 0 18px}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin:0;padding:0;list-style:none}
.meta li{font:500 12px/1 var(--sans);letter-spacing:.02em;border:1px solid var(--line-strong);border-radius:999px;padding:6px 10px;color:var(--muted);background:var(--surface)}
.meta li b{color:var(--ink);font-weight:600}
.pipeline{list-style:none;margin:22px 0 0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;counter-reset:ph -1}
.pipeline li{counter-increment:ph;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:13px;line-height:1.4;color:var(--muted)}
.pipeline li::before{content:"Phase " counter(ph);display:block;font:600 11px var(--mono);color:var(--accent);letter-spacing:.04em;text-transform:uppercase;margin-bottom:4px}
.pipeline b{display:block;color:var(--ink);font-weight:600;font-size:14px}

/* chapters */
.chapter{padding-top:40px;scroll-margin-top:12px}
.chapter+.chapter{border-top:1px solid var(--line);margin-top:28px}
.eyebrow{font:600 12px var(--mono);text-transform:uppercase;letter-spacing:.08em;color:var(--accent);margin:0 0 6px}
.chapter h2{font:700 clamp(26px,3.6vw,34px)/1.1 var(--display);margin:0 0 18px;text-wrap:balance}
.chapter h3{font:600 21px/1.25 var(--display);margin:34px 0 10px;scroll-margin-top:12px;text-wrap:balance}
.chapter h4{font:600 16px/1.3 var(--sans);margin:24px 0 8px;scroll-margin-top:12px}
.chapter p,.chapter li{max-width:72ch}
.chapter ul,.chapter ol{padding-left:1.3em}
.chapter li{margin:3px 0}
.chapter hr{border:0;border-top:1px dashed var(--line-strong);margin:28px 0}
blockquote{margin:0 0 1.2rem;padding:10px 14px;border-left:3px solid var(--effect);background:var(--effect-soft);border-radius:0 6px 6px 0}
blockquote p{margin:.3em 0}
.table-wrap{overflow-x:auto;margin:0 0 1.3rem;border:1px solid var(--line);border-radius:8px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:13.5px;line-height:1.45}
th,td{text-align:left;vertical-align:top;padding:8px 12px;border-bottom:1px solid var(--line)}
th{font-weight:600;background:var(--bg);white-space:nowrap}
tr:last-child td{border-bottom:0}
td code,th code{white-space:normal}
input[type=checkbox]{accent-color:var(--accent)}

/* PSCT anatomy */
.anatomy{margin:4px 0 22px}
.anatomy-strip{display:flex;flex-wrap:wrap;align-items:stretch;gap:0;background:var(--surface);border:1px solid var(--line-strong);border-radius:10px;padding:14px;font-family:var(--sans)}
.seg{display:flex;flex-direction:column;gap:4px;padding:8px 10px;border-radius:6px;min-width:0}
.seg b{font-weight:500;font-size:15px}
.seg i{font:600 11px var(--mono);font-style:normal;text-transform:uppercase;letter-spacing:.05em}
.seg-cond{background:var(--accent-soft)} .seg-cond i{color:var(--accent)}
.seg-cost{background:var(--effect-soft)} .seg-cost i{color:var(--effect)}
.seg-res{background:var(--trap-soft)} .seg-res i{color:var(--trap)}
.punct{font:700 26px/1 var(--mono);color:var(--ink);align-self:center;padding:0 6px}
.anatomy figcaption{font-size:13.5px;color:var(--muted);margin-top:10px;max-width:72ch}

/* highlight.js tokens */
.hljs-keyword,.hljs-built_in.hljs-keyword{color:var(--hl-kw);font-weight:600}
.hljs-string{color:var(--hl-str)}
.hljs-number{color:var(--hl-num)}
.hljs-comment{color:var(--hl-com);font-style:italic}
.hljs-title,.hljs-title.function_{color:var(--hl-fn)}
.hljs-built_in,.hljs-literal{color:var(--hl-const)}
.hljs-attr,.hljs-variable{color:var(--hl-fn)}
mark{background:var(--mark);color:inherit;border-radius:2px}

.backtop{position:fixed;right:16px;bottom:calc(16px + env(safe-area-inset-bottom,0px));font:600 12px var(--sans);background:var(--surface);color:var(--ink);border:1px solid var(--line-strong);border-radius:999px;padding:8px 12px;text-decoration:none}

@media (max-width: 900px){
  .shell{grid-template-columns:minmax(0,1fr)}
  .topbar{display:flex;position:sticky;top:env(safe-area-inset-top,0px);z-index:20;align-items:center;justify-content:space-between;gap:12px;background:var(--surface);border-bottom:1px solid var(--line);padding:10px 16px}
  .topbar b{font:700 17px var(--display)}
  .topbar button{font:600 13px var(--sans);color:var(--ink);background:var(--bg);border:1px solid var(--line-strong);border-radius:6px;padding:7px 12px}
  .side{position:fixed;z-index:30;left:0;top:0;bottom:0;width:min(86vw,320px);height:auto;transform:translateX(-102%);transition:transform .2s ease;box-shadow:0 0 0 100vmax transparent;padding-top:calc(22px + env(safe-area-inset-top,0px))}
  .side.open{transform:none;box-shadow:0 0 0 100vmax rgba(0,0,0,.35)}
  .main{padding-block:20px 96px}
}
@media (prefers-reduced-motion: reduce){.side{transition:none}}
</style>

<div class="topbar"><b>Scripting Handbook</b><button type="button" id="navToggle" aria-expanded="false" aria-controls="side">Contents</button></div>
<div class="shell">
  <nav class="side" id="side" aria-label="Chapters">
    <p class="brand">EDOPro Scripting Handbook<small>Zedja's CardScripts fork · workflow snapshot of 26 Sep 2026</small></p>
    <div class="filter"><input id="navFilter" type="search" aria-label="Filter headings" placeholder="Filter headings (e.g. count limit)" autocomplete="off"></div>
    <ol class="nav" id="nav">%%NAV%%</ol>
    <p class="nav-empty" id="navEmpty" hidden>No heading matches.</p>
    <div class="side-foot">
      <a href="%%PR%%" target="_blank" rel="noopener">Pull request #1 on GitHub</a>
      <span>Source: <code>docs/</code> in CardScripts. The repository is authoritative if this page and the files differ.</span>
    </div>
  </nav>
  <main class="main" id="top">
    <div class="content">
      <header class="hero">
        <p class="eyebrow">Yu-Gi-Oh! · EDOPro · Lua 5.4</p>
        <h1>EDOPro Scripting Handbook</h1>
        <p class="lede">How a card goes from its printed text to a verified Lua script in Zedja's CardScripts fork: reading PSCT, matching the Project Ignis house style, building database entries, and checking the result in the real ygopro-core.</p>
        <ul class="meta">
          <li><b>32</b> tested templates</li>
          <li><b>13,541</b> official scripts analysed</li>
          <li><b>3,905</b> runtime API names checked</li>
          <li>Passcodes <b>27xxxxxxx</b></li>
          <li>Credit <b>--scripted by Zedja</b></li>
        </ul>
        <ol class="pipeline" aria-label="Workflow phases">
          <li><b>Intake</b>Passcode, name or full card text</li>
          <li><b>Card data</b><code>cdb.py show</code> / <code>new</code></li>
          <li><b>Effect table</b>PSCT parsed per effect</li>
          <li><b>Analogs</b><code>cdb.py analogs</code> + cookbook</li>
          <li><b>Write</b>House style, strings, metadata</li>
          <li><b>Verify</b><code>lint.py</code>, <code>loadcheck.py</code>, test board</li>
          <li><b>Deliver</b>Commit, one PR per batch, report</li>
        </ol>
      </header>
%%SECTIONS%%
    </div>
  </main>
</div>
<a class="backtop" href="#top">Top</a>

<script src="%%HLJS%%/highlight.min.js"></script>
<script src="%%HLJS%%/languages/lua.min.js"></script>
<script>
(function(){
  if (window.hljs) {
    document.querySelectorAll('pre code[class^="language-"]').forEach(function(el){ try { hljs.highlightElement(el); } catch(e) {} });
  }
  var side = document.getElementById('side');
  var toggle = document.getElementById('navToggle');
  function closeNav(){ side.classList.remove('open'); toggle.setAttribute('aria-expanded','false'); }
  toggle.addEventListener('click', function(){
    var open = side.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  side.addEventListener('click', function(ev){ if (ev.target.closest('a[href^="#"]')) closeNav(); });
  document.addEventListener('keydown', function(ev){ if (ev.key === 'Escape') closeNav(); });

  // scrollspy: active chapter and heading
  var chItems = {};
  document.querySelectorAll('.nav-ch').forEach(function(li){ chItems[li.dataset.ch] = li; });
  var subLinks = {};
  document.querySelectorAll('.nav-sub a').forEach(function(a){ subLinks[a.getAttribute('href').slice(1)] = a; });
  var current = null, currentSub = null;
  function setChapter(id){
    if (current === id) return;
    if (current && chItems[current]) chItems[current].classList.remove('active');
    current = id;
    if (chItems[id]) chItems[id].classList.add('active');
  }
  function setSub(id){
    if (currentSub === id) return;
    if (currentSub && subLinks[currentSub]) subLinks[currentSub].classList.remove('current');
    currentSub = id;
    if (subLinks[id]) subLinks[id].classList.add('current');
  }
  var targets = Array.prototype.slice.call(document.querySelectorAll('.chapter, .chapter h3[id]'));
  function onScroll(){
    var y = 90, ch = null, sub = null;
    for (var i = 0; i < targets.length; i++) {
      var t = targets[i];
      if (t.getBoundingClientRect().top - y <= 0) {
        if (t.classList.contains('chapter')) { ch = t.id; sub = null; } else { sub = t.id; }
      } else break;
    }
    setChapter(ch || 'overview');
    setSub(sub);
  }
  var ticking = false;
  window.addEventListener('scroll', function(){
    if (!ticking) { ticking = true; requestAnimationFrame(function(){ ticking = false; onScroll(); }); }
  }, {passive:true});
  onScroll();

  // heading filter
  var input = document.getElementById('navFilter');
  var empty = document.getElementById('navEmpty');
  input.addEventListener('input', function(){
    var q = input.value.trim().toLowerCase();
    side.classList.toggle('filtering', q.length > 0);
    var any = false;
    document.querySelectorAll('.nav-ch').forEach(function(li){
      var chMatch = li.querySelector('.nav-ch-link').textContent.toLowerCase().indexOf(q) >= 0;
      var subMatch = false;
      li.querySelectorAll('.nav-sub li').forEach(function(s){
        var m = !q || chMatch || s.textContent.toLowerCase().indexOf(q) >= 0;
        s.classList.toggle('nomatch', !m);
        if (m && q) subMatch = true;
      });
      var show = !q || chMatch || subMatch;
      li.classList.toggle('nomatch', !show);
      if (show) any = true;
    });
    empty.hidden = any;
  });
})();
</script>
"""


def main():
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("-o", "--output", required=True)
	ap.add_argument("--branch", default="claude/edopro-card-scripting-workflow-qda291",
	                help="branch used for links to repository files")
	args = ap.parse_args()
	Path(args.output).write_text(build(args.branch), encoding="utf-8")
	print(f"wrote {args.output}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
