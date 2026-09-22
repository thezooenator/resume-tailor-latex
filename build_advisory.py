#!/usr/bin/env python3
"""
Resume builder (advisory variant) — picks presets for a job description using
Claude, learns from your feedback over time, and additionally reports material
it was NOT able to select.

Same selection behaviour as build.py, plus a "Suggestions" block: the model is
shown the tier-3 bullet inventory and the full course pool (neither of which it
may select) purely so it can tell you when something in there fits the job
better than what the presets can reach.  Nothing is written back to content/ —
acting on a suggestion is always a manual edit.

Shares memory.json with build.py; the entry schema is unchanged, so the two
scripts can be used interchangeably without corrupting each other's history.

Usage:
    python build_advisory.py                   # paste JD interactively
    python build_advisory.py "JD text here"    # JD as argument
    cat jd.txt | python build_advisory.py      # pipe JD in

Options:
    -a, --autofill        also build the parser-friendly version
    -c, --clipboard       read the JD from the clipboard
        --squeeze VALUE   pin the density dial (e.g. 0.85) instead of letting
                          the builder find the loosest value that fits one page
"""

import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import anthropic

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO     = Path(__file__).parent
MEMORY   = REPO / "memory.json"
PDFLATEX = shutil.which("pdflatex") or "/Library/TeX/texbin/pdflatex"
MODEL    = os.environ.get("RESUME_MODEL", "claude-opus-5")

# Generated files stay out of the repo root: sources in one folder, PDFs in
# another.  pdflatex still runs from REPO so \input{preamble} and content/*.tex
# resolve, and is handed a REPO-relative path to the source.
TEX_DIR    = REPO / "GeneratedTex"
OUTPUT_DIR = REPO / "OutputPDFs"

# ── Density ladder ────────────────────────────────────────────────────────────
# A real resume has to fit one page, and \squeeze comes before cutting content.
# The model can't see a page count, so it doesn't get to guess a value: the
# builder compiles at the top of this ladder and steps down a rung at a time
# until the PDF is one page, which lands on the loosest spacing that fits.
# 1.0 is the original Pages spacing; below 0.6 starts to look cramped, so 0.62
# is the last rung — past that the answer is a shorter preset, not more dial.
# Kept in step with build.py, which shares memory.json with this script.
SQUEEZE_LADDER = [1.0, 0.90, 0.85, 0.80, 0.72, 0.62]

# ── Preset catalog ─────────────────────────────────────────────────────────────
# When you add new presets to content/*.tex, add them here too.
# Your presets live in content/catalog.json -- the same file build.py reads.
_CATALOG_DATA = json.loads((REPO / "content" / "catalog.json").read_text())
CATALOG = _CATALOG_DATA["presets"]

# ── Catalog drift check ────────────────────────────────────────────────────────
# The catalog above is a hand-written mirror of content/*.tex.  These checks
# make drift loud instead of silent: a catalog name that no longer exists is a
# hard error, and a new preset in content/ that never got a catalog entry is a
# warning (Claude can only pick names it is shown).

CONTENT_DIR = REPO / "content"

# Commands that are neither presets nor bullets and should never be cataloged.
NON_PRESET_COMMANDS = {"Header"}


def scan_content_commands() -> dict:
    """Map every \\newcommand name in content/*.tex to the start of its body."""
    found = {}
    for tex in sorted(CONTENT_DIR.glob("*.tex")):
        text = tex.read_text()
        for m in re.finditer(r"\\newcommand\{\\(\w+)\}\{", text):
            body = text[m.end():m.end() + 120].lstrip("%").lstrip()
            found[m.group(1)] = body
    return found


def validate_catalog():
    if not CONTENT_DIR.is_dir():
        print(f"Warning: {CONTENT_DIR} not found — skipping catalog check.")
        return

    defined = scan_content_commands()
    cataloged = {name for section in CATALOG.values() for name in section}

    missing = sorted(cataloged - set(defined))
    if missing:
        print("ERROR: CATALOG names with no \\newcommand in content/*.tex:")
        for name in missing:
            print(f"    \\{name}")
        print("\nFix the spelling in build.py, or define the preset in content/.")
        sys.exit(1)

    # Preset-like = not a bullet (\item...) and not a bare entry header (\entry...).
    uncataloged = sorted(
        name for name, body in defined.items()
        if name not in cataloged
        and name not in NON_PRESET_COMMANDS
        and not body.startswith("\\item")
        and not body.startswith("\\entry")
    )
    if uncataloged:
        print("Warning: presets defined in content/ but absent from CATALOG —")
        print("         Claude cannot select these until you add them:")
        for name in uncataloged:
            print(f"    \\{name}")
        print()



# ── Advisory inventories ──────────────────────────────────────────────────────
# Everything below is DERIVED from content/*.tex, never hand-maintained, so it
# cannot drift the way CATALOG can.  It is shown to the model as reference-only
# material: it may cite these names in suggestions but may not select them.

BULLET_CHARS = 200          # per-bullet truncation, keeps the prompt bounded
COURSE_MARKER = "Others you have taken"


def _balanced(text: str, start: int) -> str:
    """Return the body starting just inside an opening brace at `start`.

    Stopping at the next \\newcommand instead would swallow the trailing comment
    lines that separate definitions in content/*.tex, so the brace is matched
    properly.  A brace preceded by a backslash is a literal, not a delimiter.
    """
    depth, i = 1, start
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    return text[start:]


def scan_content_bodies() -> dict:
    """Map every \\newcommand name in content/*.tex to (file stem, body)."""
    out = {}
    for tex in sorted(CONTENT_DIR.glob("*.tex")):
        text = tex.read_text()
        for m in re.finditer(r"\\newcommand\{\\(\w+)\}\{", text):
            out[m.group(1)] = (tex.stem, _balanced(text, m.end()))
    return out


def _readable(body: str) -> str:
    """Flatten a LaTeX bullet body into one line of plain-ish text."""
    t = body.strip()
    t = re.sub(r"^\\item\s*", "", t)
    t = t.rstrip()
    t = t.replace(r"\degsym{}", "°").replace(r"\&", "&").replace(r"\%", "%")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:BULLET_CHARS] + "…" if len(t) > BULLET_CHARS else t


def bullet_inventory() -> dict:
    """Tier-3 bullets grouped by section, flagged when no preset can reach them.

    A bullet is "unused" when no non-bullet command in content/ references it —
    i.e. there is no preset Claude could pick that would put it on the page.
    """
    bodies = scan_content_bodies()
    tier3 = {n: v for n, v in bodies.items() if v[1].lstrip().startswith(r"\item")}

    referenced = set()
    for name, (_, body) in bodies.items():
        if name not in tier3:
            referenced |= set(re.findall(r"\\(\w+)", body))

    inv = {}
    for name, (stem, body) in sorted(tier3.items()):
        tag = "" if name in referenced else "  [UNUSED — no preset reaches this]"
        inv.setdefault(stem, {})[name] = _readable(body) + tag
    return inv


def course_pool() -> dict:
    """Every course taken, flagged when it appears in no \\Courses* preset.

    Two sources, both in content/education.tex: the courses already inside the
    \\Courses* bullets, and the comment block listing the rest.  That block is
    parsed by its "Others you have taken" marker, with courses separated by
    " . " because several course names contain commas.
    """
    edu = CONTENT_DIR / "education.tex"
    if not edu.is_file():
        return {}
    text = edu.read_text()

    in_lists = []
    for m in re.finditer(r"\\newcommand\{\\Courses\w*\}\{\\item\s*Relevant Courses:\s*(.*)", text):
        line = m.group(1).rstrip().rstrip("}")
        in_lists += [c.strip() for c in line.split(",") if c.strip()]

    extras = []
    idx = text.find(COURSE_MARKER)
    if idx != -1:
        for line in text[idx:].splitlines()[1:]:
            if not line.startswith("%"):
                break
            body = line.lstrip("%").strip()
            if not body:
                break
            extras += [c.strip() for c in body.split(" . ") if c.strip()]

    pool = {}
    for c in in_lists:
        pool.setdefault(c.replace(r"\&", "&"), True)
    for c in extras:
        pool.setdefault(c.replace(r"\&", "&"), False)
    return pool


def render_inventories() -> str:
    """The reference-only block appended to the user message."""
    inv = bullet_inventory()
    lines = [
        "BULLET INVENTORY (the individual bullets that presets are built from).",
        "You CANNOT select these — they are shown only so your suggestions can",
        "name a specific bullet:",
    ]
    for section in sorted(inv):
        lines.append(f"\n  [{section}]")
        for name, text in inv[section].items():
            lines.append(f"    \\{name}: {text}")

    pool = course_pool()
    if pool:
        lines.append("\n\nCOURSE POOL (every course actually taken).  You CANNOT")
        lines.append("select these either; [UNUSED] = present in no course preset:")
        for course, used in pool.items():
            lines.append(f"    {course}" + ("" if used else "  [UNUSED]"))
    return "\n".join(lines)


SYSTEM_PROMPT = """\
You are a resume-tailoring assistant. Given a job description and a catalog of \
available resume presets, select the best combination for the role. Use past \
feedback to make better initial choices — if feedback says "prefer X over Y for \
this type of role", apply that preference.

Return ONLY valid JSON with this structure:
{
  "company": "Company name",
  "role": "Job title",
  "filename": "company_slug",
  "jd_summary": "3-5 key points from the JD: stack, seniority, domain, standout requirements",
  "education": ["PresetName", ...],
  "technical": ["PresetName", ...],
  "work": ["PresetName", ...],
  "skills": "PresetName",
  "middle_order": ["technical", "work"],
  "reasoning": "1-2 sentences on the key tradeoffs",
  "gaps": ["things the JD wants that aren't in the resume content"],
  "suggestions": [{"section": "education", "suggestion": "..."}]
}

Rules:
- technical: 2-4 items, most relevant first
- skills: exactly one preset
- middle_order: the two middle sections, most relevant to the role first —
  either ["technical", "work"] (the default) or ["work", "technical"]. Choose
  ["work", "technical"] only when the job experience is a stronger match for
  the role than the projects are. Education always comes first and skills
  always last; those are fixed and not yours to choose
- Only use preset names that exist in the catalog
- jd_summary: one compact line, under 200 characters. This is all that gets
  stored in memory, so keep the details that would change a preset choice
- length: the builder tightens line spacing automatically until the page fits,
  so don't ask for spacing changes. But past entries showing a tight fit
  (squeeze 0.72 or lower, or "still over one page") mean that much content does
  not fit — for a similar posting, prefer the shorter variants (*Short,
  *Condensed, *OneLine, one fewer technical entry)
- gaps: be honest — list specific missing technologies or experiences. A gap
  is something genuinely absent from ALL the material you were shown. If it
  appears in the bullet inventory or the course pool it is not a gap — it is a
  suggestion
- suggestions: advisory only. They change nothing about this build; they tell
  the user what a manual edit to content/ could unlock. Raise one when:
  * the JD names a course that is in the course pool but in no course preset
    (say which course, and which preset would need to change)
  * a specific bullet in the inventory fits this JD better than a bullet the
    preset you chose actually uses — name BOTH bullets, e.g. "\InternShort
    spends a line on \InternDashboard; \InternOnCall would speak more to
    the production-support angle here"
  * a bullet marked [UNUSED] is a strong match for this JD and no preset can
    currently reach it
  Only raise a suggestion when the JD gives a concrete reason. An empty list is
  a good and common answer — do not manufacture suggestions to fill the field.
  Never propose new wording: reference only names and courses you were shown\
"""
_EXTRA_RULES = _CATALOG_DATA.get("selection_rules", [])
if _EXTRA_RULES:
    SYSTEM_PROMPT += "\n" + "\n".join(f"- {r}" for r in _EXTRA_RULES)


# Section heading text.  Education always leads and skills always closes; only
# the two middle sections may swap, so MIDDLE_SECTIONS is both the set of
# reorderable names and their default order.
SECTION_HEADINGS = {
    "education": r"\section{EDUCATION}",
    "technical": r"\section{TECHNICAL EXPERIENCE}",
    "work":      r"\section{WORK EXPERIENCE}",
    "skills":    r"\section{SKILLS \& INTERESTS}",
}
MIDDLE_SECTIONS = ["technical", "work"]
DEFAULT_SECTION_ORDER = ["education"] + MIDDLE_SECTIONS + ["skills"]


# ── Memory ────────────────────────────────────────────────────────────────────
# One entry per job, not per rebuild.  Each entry stores a short JD summary
# (not the raw text) plus the first selection, the final selection, and every
# round of feedback in between — the first-vs-final delta is the learning
# signal.  Entries are small, so the context window holds many more jobs.

MEMORY_WINDOW = 40


def load_memory() -> list:
    if MEMORY.exists():
        return json.loads(MEMORY.read_text())
    return []


def save_memory(entries: list):
    MEMORY.write_text(json.dumps(entries, indent=2))


def _feedback_lines(entry: dict) -> list:
    """Feedback is a list on new entries, a bare string on pre-migration ones."""
    fb = entry.get("feedback", [])
    if isinstance(fb, str):
        fb = [fb] if fb else []
    return [f for f in fb if f]


def memory_context(entries: list) -> str:
    if not entries:
        return "No prior sessions."
    recent = entries[-MEMORY_WINDOW:]
    lines = ["Past sessions (most recent last) — use feedback to improve this selection:"]
    for e in recent:
        lines.append(f"\n[{e['timestamp'][:10]}] {e.get('company','?')} — {e.get('role','?')}")
        # Entries predating jd_summary have no usable description of the JD.  The
        # opening lines of a posting are company boilerplate, so showing those
        # would be misleading filler — company, role, and feedback carry the
        # signal instead.
        summary = e.get("jd_summary", "")
        if summary:
            lines.append(f"  JD:         {summary}")

        first = e.get("initial_selected")
        sel = e.get("selected", {})
        fb = _feedback_lines(e)

        if first and first != sel:
            lines.append(f"  first pick: education={first.get('education', [])} "
                         f"technical={first.get('technical', [])} "
                         f"work={first.get('work', [])} skills={first.get('skills', '')}")
            label = "  final:     "
        else:
            label = "  selected:  "
        lines.append(f"{label} education={sel.get('education', [])} "
                     f"technical={sel.get('technical', [])} "
                     f"work={sel.get('work', [])} skills={sel.get('skills', '')}")

        order = sel.get("order")
        if order and order != DEFAULT_SECTION_ORDER:
            lines.append(f"  order:      {' -> '.join(order)}")

        # How hard the page had to be squeezed to fit is a length signal the
        # model can act on: a tight dial means that selection was near the
        # limit, and a selection that never fit means it was over it.
        sq = sel.get("squeeze")
        if sq is not None and sq < 1.0:
            note = " (still over one page — too long)" if sel.get("pages", 1) > 1 else ""
            lines.append(f"  fit:        needed squeeze {sq:.2f} to fit one page{note}")

        if fb:
            for i, f in enumerate(fb, 1):
                lines.append(f"  feedback {i}: {f}")
        else:
            lines.append("  feedback:   (accepted as-is)")
    return "\n".join(lines)


# ── Claude ────────────────────────────────────────────────────────────────────

def call_claude(jd: str, memory: list) -> dict:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"JOB DESCRIPTION:\n{jd}\n\n"
                f"PRESET CATALOG (select ONLY from these):\n"
                f"{json.dumps(CATALOG, indent=2)}\n\n"
                f"REFERENCE ONLY — NOT SELECTABLE:\n{render_inventories()}\n\n"
                f"MEMORY:\n{memory_context(memory)}\n\n"
                "Select the best presets for this job."
            ),
        }],
    )
    raw = next(b.text for b in response.content if b.type == "text").strip()
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        if response.stop_reason == "max_tokens":
            print("Response hit max_tokens and was cut off mid-JSON. "
                  "Raise max_tokens in call_claude().")
        print(f"JSON parsing failed. Raw response:\n{raw[:1000]}")
        raise


# ── LaTeX / PDF ───────────────────────────────────────────────────────────────

def resolve_section_order(selection: dict) -> list:
    """Build the section order from the model's middle_order.

    Education is always first and skills always last; the only choice is
    whether technical or work experience comes between them.  Anything the
    model returns other than those two names is ignored, so a malformed
    response degrades to the default rather than reshaping the resume.
    """
    requested = selection.get("middle_order") or []
    middle = []
    for name in requested:
        name = str(name).strip().lower()
        if name in MIDDLE_SECTIONS and name not in middle:
            middle.append(name)

    ignored = [n for n in requested if str(n).strip().lower() not in middle]
    if ignored:
        print(f"  (ignored unusable middle_order entries: {ignored})")
    for name in MIDDLE_SECTIONS:
        if name not in middle:
            middle.append(name)

    return ["education"] + middle + ["skills"]


def generate_tex(selection: dict, filename: str, squeeze: float = 1.0,
                 autofill: bool = False) -> Path:
    bodies = {
        "education": "\n".join(f"\\{p}" for p in selection["education"]),
        "technical": "\n".join(f"\\{p}" for p in selection["technical"]),
        "work":      "\n".join(f"\\{p}" for p in selection["work"]),
        "skills":    f"\\{selection['skills']}",
    }

    sections = "".join(
        f"{SECTION_HEADINGS[name]}\n{bodies[name]}\n\n"
        for name in resolve_section_order(selection)
    )

    # The density dial is chosen by build_fitted() from the compiled page count,
    # not guessed here: at 1.0 the call is left in as a comment so the generated
    # source still shows the knob exists.
    dial = (r"\squeeze{%.2f}" % squeeze) if squeeze < 1.0 else "% \\squeeze{0.85}"
    cls = r"\documentclass[autofill]{zsresume}" if autofill \
        else r"\documentclass{zsresume}"

    tex = (
        f"% {selection.get('company','')} — {selection.get('role','')}\n"
        f"% Generated {datetime.now().strftime('%Y-%m-%d')}\n"
        f"{cls}\n"
        r"\input{preamble}" + "\n\n"
        r"\begin{document}" + "\n"
        f"{dial}\n\n"
        r"\Header" + "\n\n"
        f"{sections}"
        r"\end{document}" + "\n"
    )
    TEX_DIR.mkdir(exist_ok=True)
    path = TEX_DIR / f"{filename}.tex"
    path.write_text(tex)
    return path


def build_pdf(tex_path: Path, jobname: str = None) -> tuple:
    """Compile a .tex into OutputPDFs/ and return (pdf path, page count).

    pdflatex runs from REPO so \\input{preamble} and content/*.tex still
    resolve, but every artifact it writes lands in OUTPUT_DIR — the PDF stays
    there rather than being copied out of the repo root, and the aux/log/out
    files are cleaned up alongside it.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    stem = jobname or tex_path.stem

    cmd = [PDFLATEX, "-interaction=nonstopmode", f"-output-directory={OUTPUT_DIR}"]
    if jobname:
        cmd += [f"-jobname={jobname}"]
    cmd.append(str(tex_path.relative_to(REPO)))
    result = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)

    pdf = OUTPUT_DIR / f"{stem}.pdf"
    if not pdf.exists():
        print("Build failed. LaTeX output:\n")
        print(result.stdout[-3000:])
        sys.exit(1)

    # "Output written on ... (2 pages, 41234 bytes)" is pdflatex's own count, so
    # no extra tool is needed to know whether this run fits on one page.  It
    # hard-wraps its log at 79 columns and the absolute output path is long
    # enough to split that line, so the newlines come out before matching.
    flat = result.stdout.replace("\n", "")
    match = re.search(r"Output written on .*?\((\d+) pages?", flat)
    pages = int(match.group(1)) if match else 0

    for ext in (".aux", ".log", ".out"):
        (OUTPUT_DIR / f"{stem}{ext}").unlink(missing_ok=True)
    return pdf, pages


def build_fitted(selection: dict, filename: str, pinned: float = None,
                 autofill: bool = False, jobname: str = None) -> tuple:
    """Compile at the loosest density that still fits one page.

    Walks SQUEEZE_LADDER from 1.0 downwards, recompiling until pdflatex reports
    a single page.  Each rung is one fast pdflatex run, so the cost of finding
    the value is a few tenths of a second and the result is measured rather
    than predicted -- the failure mode this replaces was a selection quietly
    spilling onto page two with the dial never touched.

    `pinned` skips the search and compiles that value once: --squeeze on the
    command line, and the autofill build, which is deliberately allowed to run
    long and only has to match the real resume's spacing.

    Returns (pdf path, squeeze used, page count).
    """
    ladder = [pinned] if pinned is not None else SQUEEZE_LADDER

    for value in ladder:
        tex = generate_tex(selection, filename, value, autofill)
        pdf, pages = build_pdf(tex, jobname)
        if pinned is not None:
            return pdf, value, pages
        if pages == 1:
            if value < 1.0:
                print(f"  squeeze {value:.2f} — fits one page")
            return pdf, value, pages
        print(f"  {pages} pages at squeeze {value:.2f}, tightening...")

    # Out of rungs: the last (tightest) build stands, but the selection is too
    # long for the dial to rescue and the honest move is to say so rather than
    # hand over a two-page "one-page" resume.  This script can also answer it
    # from the other side -- a suggestion may be what shortens the selection.
    print(f"  ! still {pages} pages at squeeze {ladder[-1]:.2f} — the dial is "
          f"out of room. Ask for shorter presets (fewer technical bullets, or "
          f"a *Short / *OneLine variant) in the feedback prompt below.")
    return pdf, ladder[-1], pages


# ── Advisory output ───────────────────────────────────────────────────────────

def print_suggestions(suggestions: list):
    """Print the advisory block.  Purely informational — nothing acts on it."""
    if not suggestions:
        return
    print("\n  Suggestions (manual edits to content/ that could improve this):")
    for s in suggestions:
        if isinstance(s, dict):
            section = s.get("section", "")
            text = s.get("suggestion", "")
            head = f"[{section}] " if section else ""
        else:
            head, text = "", str(s)
        wrapped = textwrap.wrap(head + text, width=76,
                                initial_indent="    - ", subsequent_indent="      ")
        print("\n".join(wrapped))


def open_file(path: Path):
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    elif sys.platform.startswith("win"):
        os.startfile(str(path))
    else:
        subprocess.run(["xdg-open", str(path)], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def read_clipboard() -> str:
    for cmd in (["pbpaste"], ["wl-paste"], ["xclip", "-selection", "clipboard", "-o"],
                ["powershell", "-command", "Get-Clipboard"]):
        if shutil.which(cmd[0]):
            return subprocess.run(cmd, capture_output=True, text=True).stdout
    print("No clipboard tool found (pbpaste, wl-paste, xclip or powershell).")
    sys.exit(1)


# ── Input ─────────────────────────────────────────────────────────────────────

def parse_args():
    """Split the command line into JD arguments and density options."""
    args = sys.argv[1:]
    autofill = "--autofill" in args or "-a" in args

    # --squeeze pins the dial and turns the fit search off, for the rare case
    # where you want a specific spacing regardless of where the page ends.
    squeeze_pin = None
    if "--squeeze" in args:
        i = args.index("--squeeze")
        try:
            squeeze_pin = float(args[i + 1])
        except (IndexError, ValueError):
            print("--squeeze needs a number, e.g. --squeeze 0.85")
            sys.exit(1)
        del args[i:i + 2]

    args = [a for a in args if a not in ("--autofill", "-a")]
    return args, autofill, squeeze_pin


def read_jd(args: list) -> str:
    if "--clipboard" in args or "-c" in args:
        print("Reading job description from clipboard...")
        return read_clipboard()

    if args:
        arg = " ".join(args)
        p = Path(arg)
        if p.exists():
            return p.read_text()
        return arg

    if not sys.stdin.isatty():
        return sys.stdin.read()

    print("Tip: copy the JD first, then run:  python3 build.py --clipboard\n")
    print("Or paste it here and press Ctrl+D when done:\n")
    lines = []
    try:
        while True:
            lines.append(input())
    except EOFError:
        pass
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args, autofill, squeeze_pin = parse_args()
    jd = read_jd(args).strip()
    if not jd:
        print("No job description provided.")
        sys.exit(1)

    validate_catalog()

    memory = load_memory()
    print("Analyzing job description...")

    selection = call_claude(jd, memory)
    company  = selection.get("company", "company")
    role     = selection.get("role", "role")
    filename = selection.get("filename", "resume")
    if autofill:
        filename += "_autofill"

    def print_selection(sel):
        print(f"\n  Education:  {', '.join(sel['education'])}")
        print(f"  Technical:  {', '.join(sel['technical'])}")
        print(f"  Work:       {', '.join(sel['work'])}")
        print(f"  Skills:     {sel['skills']}")
        print(f"  Order:      {' -> '.join(resolve_section_order(sel))}")
        print(f"\n  Reasoning: {sel.get('reasoning', '')}")
        gaps = sel.get("gaps", [])
        if gaps:
            print(f"  Gaps:      {', '.join(gaps)}")
        print_suggestions(sel.get("suggestions", []))

    print(f"\n{company} — {role}")
    print_selection(selection)

    def build_both(sel):
        base = sel.get("filename", "resume")

        print(f"\nBuilding {base}.pdf...")
        pdf, used, pages = build_fitted(sel, base, pinned=squeeze_pin)
        sel["squeeze"] = used
        sel["pages"] = pages
        print(f"→ {pdf.name}")

        if autofill:
            # The autofill version is allowed to run long, so it skips the fit
            # search and just matches the real resume's spacing.
            af_name = base + "_autofill"
            print(f"Building {af_name}.pdf...")
            af_pdf, _, _ = build_fitted(sel, f"_{base}_autofill_tmp", pinned=used,
                                        autofill=True, jobname=af_name)
            (TEX_DIR / f"_{base}_autofill_tmp.tex").unlink(missing_ok=True)
            print(f"→ {af_pdf.name}")
            open_file(af_pdf)

        open_file(pdf)

    print_selection(selection)
    build_both(selection)

    # Iterative feedback loop.  A single memory entry represents this job and is
    # rewritten in place each round, so five rounds of tweaking leave one record
    # instead of five near-duplicates crowding out older jobs.
    def snapshot(sel):
        return {
            "education": sel["education"],
            "technical": sel["technical"],
            "work":      sel["work"],
            "skills":    sel["skills"],
            "order":     resolve_section_order(sel),
            # What it actually took to fit one page.  A selection that only fit
            # at 0.62 was too long, and that is worth remembering next time.
            "squeeze":   sel.get("squeeze", 1.0),
            "pages":     sel.get("pages", 0),
        }

    entry = {
        "timestamp":        datetime.now().isoformat(),
        "company":          company,
        "role":             role,
        "filename":         filename,
        "jd_summary":       selection.get("jd_summary", ""),
        "initial_selected": snapshot(selection),
        "selected":         snapshot(selection),
        "feedback":         [],
    }
    memory.append(entry)
    save_memory(memory)

    while True:
        print("\nWhat would you change? (Enter to accept, or describe changes to rebuild)")
        try:
            feedback = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            feedback = ""
            print()

        if not feedback:
            save_memory(memory)
            print("Saved to memory.")
            break

        entry["feedback"].append(feedback)
        save_memory(memory)

        print("Rebuilding...")
        selection = call_claude(jd, memory)
        print_selection(selection)
        build_both(selection)

        entry["selected"] = snapshot(selection)
        if selection.get("jd_summary"):
            entry["jd_summary"] = selection["jd_summary"]
        save_memory(memory)


if __name__ == "__main__":
    main()
