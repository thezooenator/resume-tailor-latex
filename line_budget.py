"""
Line budget -- how much vertical space each preset takes, and how much a
built page has left.

Every preset in catalog.json is compiled once, in place after the header and
one other entry, and its height recorded.  Heights are in lines: one line is \\zsBodyLead (12bp),
the distance between two lines of a bullet.  A height is rarely a whole number
because the gaps around entry headers and sections are smaller than a line.

Each height is measured twice, at normal spacing and with every gap at zero.
\\squeeze only scales those gaps, so the difference ("flex") is exactly what
tightening can win back: at squeeze s, a preset takes lines - (1 - s) * flex.

Results are cached in preset_heights.json and re-measured automatically when
anything that affects layout changes (content/, catalog.json, style files,
class, preamble, or the TeX engine).

Shared by build.py and build_advisory.py.
"""

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

REPO    = Path(__file__).parent
CACHE   = REPO / "preset_heights.json"
CATALOG = REPO / "content" / "catalog.json"

# A good page, at normal spacing: up to SLACK lines left at the bottom (some
# white space is fine), or up to OVER lines too long (tighter spacing absorbs
# that without looking cramped).
SLACK = 2.0
OVER  = 1.5

# Every file whose change can move a line break or a gap.
_LAYOUT_FILES = ["zsresume.cls", "preamble.tex", "style.tex"]
_LAYOUT_GLOBS = ["content/*.tex", "styles/*.tex"]

# \typeout markers.  \pagetotal only counts material the page builder has
# taken in; \par then \penalty10000 hands it everything so far without
# allowing a page break.
_SNAP = r"\par\penalty10000\typeout{ZSH %s \the\pagetotal}"


def _fingerprint(pdflatex: str) -> str:
    h = hashlib.sha256(Path(pdflatex).name.encode())
    files = [REPO / f for f in _LAYOUT_FILES] + [CATALOG]
    for g in _LAYOUT_GLOBS:
        files += sorted(REPO.glob(g))
    for f in files:
        if f.exists():
            h.update(f.name.encode() + f.read_bytes())
    return h.hexdigest()[:16]


def _pt_to_lines(pt: float, lead_bp: float) -> float:
    return pt * 72 / 72.27 / lead_bp


def _measure(names: list, pdflatex: str) -> dict:
    """One pdflatex run per spacing, one page per preset."""
    runs = {}
    for label, squeeze in (("normal", None), ("flat", r"\squeeze{0}")):
        # Everything is measured where it really sits: after the header and
        # an entry, since space at the top of a page is discarded and the
        # gap above a section heading depends on what precedes it.
        lead_in = f"\\Header\\section{{EDUCATION}}\\{names[0]}"
        pages = ["\\Header\\section{EDUCATION}" + _SNAP % "header",
                 lead_in + _SNAP % "sec0" + "\\section{WORK}" + _SNAP % "sec1"]
        for n in names:
            pages.append(lead_in + _SNAP % f"start:{n}"
                         + f"\n\\{n}" + _SNAP % f"end:{n}")
        body = "\n\\clearpage\n".join(pages)
        tex = (
            "\\documentclass{zsresume}\n\\input{preamble}\n"
            "\\begin{document}\n" + (squeeze or "") + "\n"
            "\\typeout{ZSH lead \\the\\zsBodyLead}"
            "\\typeout{ZSH page \\the\\textheight}\n"
            + body + "\n\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "measure.tex"
            src.write_text(tex)
            out = subprocess.run(
                [pdflatex, "-interaction=nonstopmode", f"-output-directory={tmp}", str(src)],
                cwd=REPO, capture_output=True, text=True).stdout
        vals = {}
        for key, pt in re.findall(r"ZSH (\S+) ([\d.]+)pt", out.replace("\n", "")):
            vals[key] = float(pt)
        if "lead" not in vals or "page" not in vals:
            raise RuntimeError(
                f"Could not measure preset heights: {pdflatex} did not run. "
                f"Check that LaTeX is installed and that the example builds.")
        runs[label] = vals

    normal, flat = runs["normal"], runs["flat"]
    lead = normal["lead"] * 72.27 / 72      # bp
    lines = lambda pt: round(_pt_to_lines(pt, lead), 2)

    def entry(n_norm, n_flat):
        return {"lines": lines(n_norm), "flex": lines(n_norm - n_flat)}

    presets = {}
    for n in names:
        try:
            h_norm = normal[f"end:{n}"] - normal[f"start:{n}"]
            h_flat = flat[f"end:{n}"] - flat[f"start:{n}"]
        except KeyError:
            continue        # did not compile; build.py's catalog check reports it
        presets[n] = entry(h_norm, h_flat)

    return {
        "page":    lines(normal["page"]),
        "header":  entry(normal["header"], flat["header"]),
        "section": entry(normal["sec1"] - normal["sec0"],
                         flat["sec1"] - flat["sec0"]),
        "presets": presets,
    }


def load_heights(pdflatex: str) -> dict:
    """Heights of every catalog preset, re-measured only when layout changes."""
    presets = json.loads(CATALOG.read_text())["presets"]
    names = sorted(n for section in presets.values() for n in section)
    key = _fingerprint(pdflatex)
    if CACHE.exists():
        cached = json.loads(CACHE.read_text())
        if cached.get("fingerprint") == key:
            return cached
    print("Measuring preset heights (content or style changed)...")
    data = {"fingerprint": key, **_measure(names, pdflatex)}
    CACHE.write_text(json.dumps(data, indent=2))
    return data


def annotate_catalog(catalog: dict, heights: dict) -> dict:
    """The catalog with each description prefixed by its height."""
    p = heights["presets"]
    return {
        section: {
            name: (f"[{p[name]['lines']:.1f} lines] {desc}" if name in p else desc)
            for name, desc in presets.items()
        }
        for section, presets in catalog.items()
    }


def budget_text(heights: dict, n_sections: int = 4) -> str:
    """The page budget, as the model is told it."""
    fixed = heights["header"]["lines"] + (n_sections - 1) * heights["section"]["lines"]
    room = heights["page"] - fixed
    return (
        f"The page holds {heights['page']:.1f} lines. The header and section "
        f"headings take {fixed:.1f}, leaving {room:.1f} lines for presets. "
        f"Choose presets totalling {room - SLACK:.1f} to {room + OVER:.1f} "
        f"lines: a little white space at the bottom is fine, and a small "
        f"overrun is absorbed by tighter spacing. Beyond {room + OVER:.1f} the "
        f"page looks cramped or spills onto two."
    )


def describe_free(free: float) -> str:
    """'1.2 lines free' / '0.8 lines over' at normal spacing, flagged if outside the range."""
    text = (f"{free:.1f} lines free" if free >= 0 else f"{-free:.1f} lines over") \
        + " at normal spacing"
    if free > SLACK:
        text += " — room for a longer preset"
    elif free < -OVER:
        text += " — too long, pick shorter presets"
    return text


def predict_free(selection: dict, heights: dict, n_sections: int = 4) -> float:
    """Lines left at the bottom at normal spacing (negative = over)."""
    p = heights["presets"]
    names = (selection.get("education", []) + selection.get("technical", [])
             + selection.get("work", []) + [selection.get("skills", "")])
    used = heights["header"]["lines"] + (n_sections - 1) * heights["section"]["lines"]
    used += sum(p[n]["lines"] for n in names if n in p)
    return round(heights["page"] - used, 1)
