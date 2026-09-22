# Tailored LaTeX Resume

A one-page LaTeX resume system built for tailoring to each job. You write every
bullet once, group bullets into presets, and a short version file picks the
presets for a given role. You can optionally paste in a job description and
`build.py` asks Claude to pick the presets, then compiles the resume at the
loosest spacing that still fits on one page.

![Example output](example.png)

All content in `content/` belongs to a fictional example person. Replace it
with your own.

## Quick start

```bash
# macOS: brew install --cask basictex   ·   Linux: apt install texlive-latex-extra
pdflatex example.tex
```

To use the job-description builder:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 build.py --clipboard      # copy a job description first
```

| flag | effect |
|---|---|
| `-c`, `--clipboard` | read the JD from the clipboard (otherwise: argument, file path, stdin, or paste) |
| `-a`, `--autofill` | also build the parser-friendly version |
| `-s`, `--skills-early` | put skills directly under education |
| `--skills-late` | force skills last (overrides `-s`) |
| `--squeeze 0.85` | pin the spacing instead of searching for the loosest value that fits |

Set `RESUME_MODEL` to use a different Claude model.

After each build it asks *"What would you change?"*. Describe the change in
plain English and it rebuilds. Each job's first pick, final pick and your
feedback are saved to `memory.json`, and later runs use that history to make
better first picks. `memory.json` is gitignored so your job search stays private.

`build_advisory.py` works the same way and adds a **Suggestions** block. It
points out bullets or courses in `content/` that no preset uses yet but that
would fit the posting better. It never writes new wording.

## Layout

```
example.tex        a complete resume -- just a list of presets
skills_early.tex   same, with a grouped skills block under education
autofill.tex       plain layout for job-site resume parsers
template.tex       every preset, commented out -- copy this to start a version

content/
  education.tex    \Header (your name/contact) + education presets
  technical.tex    projects / research
  work.tex         jobs
  skills.tex       skills blocks
  catalog.json     describes each preset for build.py

zsresume.cls       the layout; rarely needs editing
preamble.tex       loads content/
build.py           JD -> Claude picks presets -> fitted one-page PDF
```

Generated sources go to `GeneratedTex/` and PDFs to `OutputPDFs/`. Both are gitignored.

## Three levels of control

Content in `content/*.tex` has three tiers:

```latex
% TIER 3 -- individual bullets
\newcommand{\InternService}{\item Built an internal Python service that ...}
\newcommand{\InternDashboard}{\item Shipped a React dashboard used daily ...}

% TIER 2 -- the entry header line
\newcommand{\InternEntry}{\entry{Acme Logistics}{Software Engineering Intern}{Springfield, ST | June 2025 - Aug 2025}}

% TIER 1 -- presets, built FROM the bullets
\newcommand{\InternShort}{\InternEntry\begin{bullets}\InternService\InternDashboard\end{bullets}}
```

A version file just lists presets:

```latex
\section{WORK EXPERIENCE}
\InternShort
\TA
```

When no preset fits, you can build the entry by hand:

```latex
\InternEntry
\begin{bullets}
  \InternServiceImpact
  \InternOnCall
\end{bullets}
```

Because presets reference bullets and don't copy them, editing a bullet's
wording once updates every preset and version that uses it, including the
autofill resume.

**New wording goes in as a new variant alongside the old one**, e.g.
`\InternServiceImpact` next to `\InternService`. Don't overwrite the old
wording. That way older versions keep building.

## Making it yours

1. Edit `\Header` in `content/education.tex` with your name and contact details.
2. Replace the entries in `content/*.tex` with your own, following the three tiers.
3. Update `content/catalog.json` so each preset has a one-line description.
   Claude can only choose from what's listed there. `build.py` exits with an
   error if the catalog names a preset that doesn't exist, and warns if a
   preset is missing from the catalog.
4. Add any rules specific to you under `selection_rules`, e.g.
   `"work: always include some version of the internship"`.
5. If you use grouped skills blocks, map each flat block to its grouped
   counterpart in `grouped_skills` / `flat_skills`.
6. Update `template.tex` and `example.tex` to use your preset names.

To keep your real resume private, keep your filled-in copy in a separate
private repo or folder. Don't push it to a public fork.

## Fitting on one page

`\squeeze{0.85}` tightens the gaps *between* entries and sections. It never
changes the leading inside a bullet, so text stays readable. `1.0` is the
default spacing, `0.85` buys about two lines, and below `0.6` it looks cramped.

`build.py` finds this value for you. It compiles at `1.0`, reads the page count
from pdflatex, and steps down `1.0, 0.90, 0.85, 0.80, 0.72, 0.62` until the
resume fits on one page. If even the tightest step spills over, it says so. At
that point, ask for shorter presets in the feedback prompt.

## The autofill version

`\documentclass[autofill]{zsresume}` uses the same content with a
parser-friendly layout. Dates run inline instead of flush right, bullets are
plain hyphens in the text flow, there are no rules, and everything is one font
size. It also prints the `\linkedin{}` and `\phoneplain{}` fields from
`\Header`. Length is unconstrained, so make it fuller than your real resume.
Always check what the job site filled in.

## Using it with Claude Code or Overleaf

**Claude Code:** open this folder and paste a job description. `CLAUDE.md`
tells it the ground rules. It can only reorder, select and trim existing
bullets. If a posting asks for something that isn't in `content/`, Claude
reports it as a gap and doesn't invent a claim.

**Overleaf:** New Project → Upload Project → upload this folder as a zip. The
compiler stays on pdfLaTeX. Overleaf can also sync with a GitHub repo.

## Notes

- Dimensions in the class are in `bp` (1/72 in, what PDF uses), not LaTeX's `pt`
  (1/72.27 in). If you add spacing, write `12bp`.
- Escape `&` `%` `#` `_` `$` as `\&` `\%` `\#` `\_` `\$`. Helpers: `\sm` (~),
  `\arr` (→), `\x` (×), `\degsym` (°).
- The font is Nimbus Roman (`mathptmx`), a free Times clone with the same
  character widths as Times New Roman.
