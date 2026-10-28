#!/usr/bin/env python3
"""
Resume builder — picks presets for a job description using Claude,
learns from your feedback over time.

Usage:
    python build.py                   # paste JD interactively
    python build.py "JD text here"    # JD as argument
    cat jd.txt | python build.py      # pipe JD in

Options:
    -a, --autofill        also build the parser-friendly version
    -s, --skills-early    skills block directly after education, above both
                          experience sections
        --skills-late     force the normal layout (skills last)
                          omit both and the model decides from the JD
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
from datetime import datetime
from pathlib import Path

import anthropic

import line_budget as lb

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO     = Path(__file__).parent
MEMORY   = REPO / "memory.json"
MEMORY_SUMMARY = REPO / "memory_summary.json"
# The TeX engine on PATH, falling back to where MacTeX/BasicTeX install it.
# RESUME_TEX=xelatex (or lualatex) is needed for \SetSystemFont in style.tex.
_ENGINE  = os.environ.get("RESUME_TEX", "pdflatex")
PDFLATEX = shutil.which(_ENGINE) or f"/Library/TeX/texbin/{_ENGINE}"
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
SQUEEZE_LADDER = [1.0, 0.90, 0.85, 0.80, 0.72, 0.62]

# ── Preset catalog ─────────────────────────────────────────────────────────────
# Everything specific to YOUR resume lives in content/catalog.json, next to the
# .tex it describes, so this script stays generic:
#   presets          section -> {PresetName: one-line description for Claude}
#   selection_rules  extra rules appended to the system prompt
#   grouped_skills   flat skills preset -> grouped block (skills-early layout)
#   flat_skills      the inverse, for when skills-early is forced off
# When you add new presets to content/*.tex, add them to catalog.json too.
CATALOG_FILE = REPO / "content" / "catalog.json"


def load_catalog_file() -> dict:
    if not CATALOG_FILE.exists():
        print(f"ERROR: {CATALOG_FILE} not found. See README.md for its format.")
        sys.exit(1)
    return json.loads(CATALOG_FILE.read_text())


_CATALOG_DATA = load_catalog_file()
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
        print("\nFix the spelling in content/catalog.json, or define the preset in content/.")
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
  "skills_early": false,
  "reasoning": "1-2 sentences on the key tradeoffs",
  "gaps": ["things the JD wants that aren't in the resume content"]
}

Rules:
- technical: 2-4 items, most relevant first
- skills: exactly one preset
- middle_order: the two middle sections, most relevant to the role first —
  either ["technical", "work"] (the default) or ["work", "technical"]. Choose
  ["work", "technical"] only when the job experience is a stronger match for
  the role than the projects are
- skills_early: false is the default layout — education, the two experience
  sections, then skills last. true moves the skills block up directly under
  education, above both experience sections — for skills-based hiring, where
  the posting lists specific technologies and cares less about the degree.
  Education leads the page either way. When true, pick one of the grouped
  skills presets (SkillsGrouped*), which are built to carry that position;
  when false, pick a flat one. The
  command line can override this either way, so choose what the JD warrants
- Only use preset names that exist in the catalog
- jd_summary: one compact line, under 200 characters. This is all that gets
  stored in memory, so keep the details that would change a preset choice
- gaps: be honest — list specific missing technologies or experiences
- length: every preset shows its measured height as [N lines], and the
  PAGE BUDGET says how many lines the presets may total. Plan to that budget
  instead of guessing from bullet counts. The builder tightens spacing
  automatically for small overruns, so don't ask for spacing changes\
"""
# Rules specific to your content (which entries always appear, which presets
# need care) come from catalog.json rather than being written in here.
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

# catalog.json may rename any heading: "section_headings": {"work":
# "Experience", "skills_early": "Skills", ...}.  Plain text is escaped for
# & and %; anything else is passed to LaTeX as written.
def _heading(text: str) -> str:
    return r"\section{" + text.replace("\\&", "&").replace("&", r"\&").replace("%", r"\%") + "}"
# Promoted out of last place, the skills block is the claim being made rather
# than a footnote of hobbies, so the heading changes with the position.
SKILLS_EARLY_HEADING = r"\section{TECHNICAL SKILLS}"
_custom = _CATALOG_DATA.get("section_headings", {})
for _key, _text in _custom.items():
    if _key == "skills_early":
        SKILLS_EARLY_HEADING = _heading(_text)
    elif _key in SECTION_HEADINGS:
        SECTION_HEADINGS[_key] = _heading(_text)
MIDDLE_SECTIONS = ["technical", "work"]
DEFAULT_SECTION_ORDER = ["education"] + MIDDLE_SECTIONS + ["skills"]

# Flat skills preset -> the grouped block that replaces it in skills-early
# layout.  Used when the command line forces skills-early after the model has
# already picked a flat preset.  FLAT_SKILLS is the inverse, for when
# skills-early is forced off.  Both come from catalog.json.
GROUPED_SKILLS = _CATALOG_DATA.get("grouped_skills", {})
FLAT_SKILLS    = _CATALOG_DATA.get("flat_skills", {})


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


# ── Long-term memory ─────────────────────────────────────────────────────────
# Only the last MEMORY_WINDOW sessions go into the prompt verbatim.  Sessions
# older than that are not dropped: before they leave the window, Claude folds
# them into a running summary of durable lessons, which rides along with every
# prompt.  memory.json itself is never trimmed -- the summary file records how
# many of its oldest entries have been folded in, so each session is
# summarized exactly once.

SUMMARY_PROMPT = """\
You maintain the long-term memory of a resume-tailoring assistant that picks \
resume presets for job descriptions. You are given the current long-term \
summary (possibly empty) and older sessions that are about to leave the \
assistant's recent-session window. Return an updated summary of durable \
lessons: which presets suit which kinds of roles, corrections the user made \
and the preferences behind them, and page-length lessons. Merge with the \
existing summary; where newer feedback contradicts older, keep the newer. \
Drop one-off details such as individual company names. Plain bullet list \
starting with "- ", at most 15 bullets, under 1500 characters. Return only \
the list.\
"""


def load_summary() -> dict:
    if MEMORY_SUMMARY.exists():
        return json.loads(MEMORY_SUMMARY.read_text())
    return {"summary": "", "summarized_through": 0}


def refresh_long_term_memory(entries: list) -> None:
    """Fold sessions that have aged out of the window into the summary."""
    state = load_summary()
    if state["summarized_through"] > len(entries):
        # memory.json was cleared or replaced; the summary describes sessions
        # that no longer exist, so start over.
        MEMORY_SUMMARY.unlink()
        state = load_summary()
    cutoff = max(0, len(entries) - MEMORY_WINDOW)
    start = state["summarized_through"]
    if cutoff <= start:
        return

    aged_out = entries[start:cutoff]
    print(f"Summarizing {len(aged_out)} older session(s) into long-term memory...")
    sessions = "\n".join(line for e in aged_out for line in _entry_lines(e))
    try:
        response = anthropic.Anthropic().messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SUMMARY_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"CURRENT SUMMARY:\n{state['summary'] or '(empty)'}\n\n"
                    f"SESSIONS TO FOLD IN:\n{sessions}"
                ),
            }],
        )
    except anthropic.APIError as err:
        # A failed summary should never block a build; these sessions are
        # retried next run.
        print(f"Warning: long-term memory not updated ({err}).")
        return

    summary = next((b.text for b in response.content if b.type == "text"), "").strip()
    if not summary:
        print("Warning: long-term memory not updated (empty summary).")
        return
    MEMORY_SUMMARY.write_text(json.dumps(
        {"summary": summary, "summarized_through": cutoff}, indent=2))


def memory_context(entries: list) -> str:
    if not entries:
        return "No prior sessions."
    lines = []
    summary = load_summary()
    if summary["summary"]:
        lines.append(f"Long-term lessons (summarized from "
                     f"{summary['summarized_through']} older sessions; the selection "
                     f"rules take precedence where they conflict):")
        lines.append(summary["summary"])
        lines.append("")
    lines.append("Past sessions (most recent last) — use feedback to improve this selection:")
    for e in entries[-MEMORY_WINDOW:]:
        lines.extend(_entry_lines(e))
    return "\n".join(lines)


def _entry_lines(e: dict) -> list:
    """One session rendered for a prompt: JD, picks, fit, and feedback."""
    lines = [f"\n[{e['timestamp'][:10]}] {e.get('company','?')} — {e.get('role','?')}"]
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
    free = sel.get("free_lines")
    if free is not None:
        lines.append(f"  space:      {lb.describe_free(free)}")

    if fb:
        for i, f in enumerate(fb, 1):
            lines.append(f"  feedback {i}: {f}")
    else:
        lines.append("  feedback:   (accepted as-is)")
    return lines


# ── Claude ────────────────────────────────────────────────────────────────────

def call_claude(jd: str, memory: list) -> dict:
    client = anthropic.Anthropic()
    heights = lb.load_heights(PDFLATEX)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"JOB DESCRIPTION:\n{jd}\n\n"
                f"PRESET CATALOG:\n{json.dumps(lb.annotate_catalog(CATALOG, heights), indent=2)}\n\n"
                f"PAGE BUDGET:\n{lb.budget_text(heights)}\n\n"
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

def skills_run_early(selection: dict) -> bool:
    """Whether the skills block runs directly after education.

    Set by the model's skills_early, overridden by --skills-early /
    --skills-late.  Anything non-boolean degrades to False, the normal layout.

    lead_with_skills is the old name for this field, from when the layout put
    skills above education rather than below it.  Memory entries written then
    still carry it, so it is still read -- the position it selects has moved,
    but "skills up front" is what it meant and still means.
    """
    if selection.get("skills_early") is True:
        return True
    return selection.get("lead_with_skills") is True


def apply_skills_early(selection: dict, forced=None):
    """Settle the layout and move the skills preset to match it.

    `forced` is the command-line flag: True or False overrides the model,
    None leaves the model's own skills_early standing.

    Either way the skills preset is then reconciled with the layout, because
    the two can disagree -- the flag is applied after the model has answered,
    and the model can also pick a mismatched pair on its own.  A flat two-line
    block stranded at the top of the page, or a five-line grouped block sitting
    at the bottom where it costs lines it no longer earns, is worth swapping
    for the counterpart in the same flavour, out loud rather than silently.
    """
    early = skills_run_early(selection) if forced is None else forced
    selection["skills_early"] = early
    selection.pop("lead_with_skills", None)
    table = GROUPED_SKILLS if early else FLAT_SKILLS
    swapped = table.get(selection.get("skills"))
    if swapped:
        print(f"  (skills-early {'on' if early else 'off'}: "
              f"{selection['skills']} -> {swapped})")
        selection["skills"] = swapped


def resolve_section_order(selection: dict) -> list:
    """Build the section order from the model's middle_order.

    Technical and work experience are the two sections that may swap, and they
    stay together in the middle of the page either way.  Education always
    leads.  The only other choice is where the skills block sits: last by
    default, or directly under education -- above both experience sections --
    when skills_early is set.  Anything the model returns other than those two
    middle names is ignored, so a malformed response degrades to the default
    rather than reshaping the resume.
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

    if skills_run_early(selection):
        return ["education", "skills"] + middle
    return ["education"] + middle + ["skills"]


def generate_tex(selection: dict, filename: str, squeeze: float = 1.0,
                 autofill: bool = False) -> Path:
    bodies = {
        "education": "\n".join(f"\\{p}" for p in selection["education"]),
        "technical": "\n".join(f"\\{p}" for p in selection["technical"]),
        "work":      "\n".join(f"\\{p}" for p in selection["work"]),
        "skills":    f"\\{selection['skills']}",
    }

    order = resolve_section_order(selection)
    headings = dict(SECTION_HEADINGS)
    if skills_run_early(selection):
        headings["skills"] = SKILLS_EARLY_HEADING

    sections = "".join(
        f"{headings[name]}\n{bodies[name]}\n\n"
        for name in order
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
    # hand over a two-page "one-page" resume.
    print(f"  ! still {pages} pages at squeeze {ladder[-1]:.2f} — the dial is "
          f"out of room. Ask for shorter presets (fewer technical bullets, or "
          f"a *Short / *OneLine variant) in the feedback prompt below.")
    return pdf, ladder[-1], pages


def open_file(path: Path):
    """Open a PDF in the system viewer, wherever that is."""
    if sys.platform == "darwin":
        cmd = ["open", str(path)]
    elif sys.platform.startswith("win"):
        os.startfile(str(path))  # noqa: only exists on Windows
        return
    else:
        cmd = ["xdg-open", str(path)]
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def read_clipboard() -> str:
    candidates = [["pbpaste"], ["wl-paste"], ["xclip", "-selection", "clipboard", "-o"],
                  ["powershell", "-command", "Get-Clipboard"]]
    for cmd in candidates:
        if shutil.which(cmd[0]):
            return subprocess.run(cmd, capture_output=True, text=True).stdout
    print("No clipboard tool found (pbpaste, wl-paste, xclip or powershell).")
    sys.exit(1)


# ── Input ─────────────────────────────────────────────────────────────────────

def parse_args():
    """Split the command line into JD arguments, layout and density options.

    skills_early is three-state on purpose: True forces the skills-early
    layout, False forces the normal one, and None leaves the call to the model
    (and to whatever the feedback loop has taught it).

    --skills-first and --skills-last are the old spellings of the two flags,
    still accepted so existing aliases and notes keep working.
    """
    args = sys.argv[1:]
    autofill = "--autofill" in args or "-a" in args

    skills_early = None
    if {"--skills-early", "--skills-first", "-s"} & set(args):
        skills_early = True
    if {"--skills-late", "--skills-last"} & set(args):
        # Explicitly asking for the normal layout wins over -s, so a shell
        # alias carrying -s can still be overridden on the command line.
        skills_early = False

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

    flags = ("--autofill", "-a", "-s",
             "--skills-early", "--skills-first", "--skills-late", "--skills-last")
    args = [a for a in args if a not in flags]
    return args, autofill, skills_early, squeeze_pin


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
    args, autofill, skills_early, squeeze_pin = parse_args()
    jd = read_jd(args).strip()
    if not jd:
        print("No job description provided.")
        sys.exit(1)

    validate_catalog()

    memory = load_memory()
    refresh_long_term_memory(memory)
    print("Analyzing job description...")

    selection = call_claude(jd, memory)
    apply_skills_early(selection, skills_early)
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
        print(f"  Order:      {' -> '.join(resolve_section_order(sel))}"
              f"{'   [skills-early]' if skills_run_early(sel) else ''}")
        print(f"\n  Reasoning: {sel.get('reasoning', '')}")
        gaps = sel.get("gaps", [])
        if gaps:
            print(f"  Gaps:      {', '.join(gaps)}")

    print(f"\n{company} — {role}")
    print_selection(selection)

    def build_both(sel):
        base = sel.get("filename", "resume")

        print(f"\nBuilding {base}.pdf...")
        pdf, used, pages = build_fitted(sel, base, pinned=squeeze_pin)
        sel["squeeze"] = used
        sel["pages"] = pages
        sel["free_lines"] = lb.predict_free(sel, lb.load_heights(PDFLATEX))
        print(f"→ {pdf.name}  ({lb.describe_free(sel['free_lines'])})")

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
            "skills_early": skills_run_early(sel),
            # What it actually took to fit one page.  A selection that only fit
            # at 0.62 was too long, and that is worth remembering next time.
            "squeeze":   sel.get("squeeze", 1.0),
            "pages":     sel.get("pages", 0),
            "free_lines": sel.get("free_lines"),
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
        apply_skills_early(selection, skills_early)
        print_selection(selection)
        build_both(selection)

        entry["selected"] = snapshot(selection)
        if selection.get("jd_summary"):
            entry["jd_summary"] = selection["jd_summary"]
        save_memory(memory)


if __name__ == "__main__":
    main()
