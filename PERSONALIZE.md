# Personalizing this repo: instructions for an AI assistant

You are helping someone turn this template into **their** resume system. They
have put one or more existing resumes in `my_resumes/` (PDF, DOCX, TXT, MD or
LaTeX), usually several versions aimed at different kinds of roles. Your job is
to move their real content into `content/*.tex` using this repo's structure,
and remove the fictional example person, Jordan Lee.

Read `README.md` for how the system works. This file is the procedure.

## Ground rules

1. **Never invent a claim.** Each bullet has to trace back to text in
   `my_resumes/` or to something the user told you in this conversation.
   Don't add numbers, technologies, titles or dates you haven't seen.
2. **Keep every distinct wording.** When two resume versions describe the same
   work differently, keep both as separate bullet variants. Don't pick a winner
   and delete the other. The variants are what makes tailoring possible later.
3. **Condensing is allowed, but it has to be flagged.** You may write a shorter
   variant that merges or trims existing bullets, as long as it adds no new
   facts. Put `% AI-condensed from \X + \Y — review` on the line above it and
   list it in your final report.
4. **Ask instead of guessing.** Ask about contact details, conflicting dates or
   titles between versions, and anything ambiguous.
5. **Treat it as private.** `my_resumes/` and `memory.json` are gitignored.
   Once `content/` holds real data, remind the user not to push it to a
   public repo.

## Procedure

### 1. Read and inventory

Read every file in `my_resumes/`. For PDFs and DOCX files, extract the text
with whatever tools you have (`pdftotext`, `python-docx`, reading the file
directly). Build an inventory:

- **Header:** name, address, phone, email, LinkedIn/website.
- **Entries:** every school, job, project or research position. For each,
  record the organization, role/detail, location, dates, and **every distinct
  bullet wording across all versions**, noting which version used which.
- **Skills:** each version's skills lines, as written.
- **Version profiles:** for each input resume, what kind of role it targets
  (e.g. "robotics", "backend web", "data science") and its section order.
- **Look:** font family (serif or sans), accent color if any, header
  alignment, paper size (A4 or US Letter), and roughly how dense it is.

If the versions contradict each other (different dates, GPA or title), ask the
user which one is correct.

### 2. Map to sections

`build.py` works with exactly four sections: `education`, `technical`
(projects and research), `work`, and `skills`. Put each entry in the closest
one. If the user has sections like Leadership, Publications or Volunteering,
put them in whichever of `technical` or `work` fits, and rename the section
headings through `section_headings` in `content/catalog.json`, e.g.
`"technical": "PROJECTS & RESEARCH"`. Tell the user what you mapped where.
Hand-written version files (`*.tex` at the root) can use any `\section{...}`
they like. The four-section limit only applies to `build.py`.

### 3. Write `content/*.tex`

Replace the example content completely, following the three tiers the
existing files show:

```latex
% TIER 2 -- entry header: \entry{Organization}{detail, in italics}{Location | Dates}
\newcommand{\AcmeEntry}{\entry{Acme Corp}{Software Engineer}{Boston, MA | 2023 - 2025}}

% TIER 3 -- one \newcommand per bullet, each starting with \item
\newcommand{\AcmeBilling}{\item Rebuilt the billing service ...}
\newcommand{\AcmeBillingShort}{\item Rebuilt billing ...}   % variant wording, same claim

% TIER 1 -- presets, built only by referencing tier-3 bullets
\newcommand{\AcmeFull}{\AcmeEntry\begin{bullets}\AcmeBilling\AcmeOnCall\end{bullets}}
\newcommand{\AcmeShort}{\AcmeEntry\begin{bullets}\AcmeBillingShort\end{bullets}}
```

- **Command names** are CamelCase letters only. LaTeX command names can't
  contain digits, so write `\GoTwoLine`, not `\Go2Line`. Prefix each command
  with its entry, like `\Acme...`. Every name has to be unique across all
  content files.
- **Escape** `& % # _ $` as `\& \% \# \_ \$`. Use `\sm` for ~, `\arr` for →,
  `\x` for × and `\degsym` for °.
- **Presets:** for each entry, create presets that reproduce what each input
  version used. Then add length options if they make sense: `Full` (every
  bullet), `Short` (2 bullets), `OneLine` (1 merged bullet, flagged per rule 3).
  Name role-flavored presets after their emphasis, e.g. `\AcmeBackend` or
  `\AcmeLeadership`.
- **Line fit:** a bullet that wraps to 1.1–1.4 lines wastes most of a line.
  Where a tighter or looser existing wording is available, prefer that variant
  in the presets. Don't invent wording just to improve the fit.
- **Education:** put course lists in `\Courses...` bullets, one per version.
  Add any courses that appear in some version but not others to the
  `% Others you have taken` comment block, separated by ` . `.
  `build_advisory.py` reads that block.
- **Skills (`content/skills.tex`):** create one flat block per distinct skills
  line in the inputs, using `\begin{skills}\skill{Label}{items}\end{skills}`.
  If the user wants the skills-early layout, add grouped blocks
  (`\SkillsGrouped...`) that only reorganize items already listed somewhere.
- **`\Header`:** use their real details. `\linkedin{}` and `\phoneplain{}` only
  appear on the autofill version.

### 4. Write `content/catalog.json`

This is the only thing `build.py`'s model sees when it picks presets, so the
descriptions matter.

- `presets`: every tier-1 preset, grouped by section. Each description gives
  the organization, the stack in parentheses, the bullet count, and what each
  bullet covers, including key numbers. Also say when a preset suits a
  particular kind of role.
- `selection_rules`: the user's standing preferences, e.g. "work: always
  include some version of Acme" or "education: the University entry always,
  the high school only for internships". Ask the user about these.
- `grouped_skills` / `flat_skills`: map each flat skills block to its grouped
  counterpart and back, if grouped blocks exist. Otherwise use `{}`.
- `section_headings`: include this if the user's headings differ from the
  defaults.

Then check it for drift:

```bash
python3 -c "import build; build.validate_catalog()"
```

This needs `pip install -r requirements.txt`. It exits with an error if the
catalog names a missing preset, and warns about presets you forgot to list.

### 5. Version files

- Replace `example.tex` with one root `.tex` file per input resume, named after
  its focus (e.g. `backend.tex`, `robotics.tex`), that recreates that resume
  using the new presets. Version files contain **no wording**, only preset
  names and `\section{}` lines. Update `CLAUDE.md`'s build line to name one of
  them.
- Update `skills_early.tex` and `autofill.tex` to use real presets. The
  autofill version should be fuller: every entry, at its longest preset.
- Rewrite the menu in `template.tex` so it lists every preset and bullet.

### 6. Style

Recreate their old look in `style.tex`. Start from the closest file in
`styles/` and override from there:

- Serif fonts: `\SetFont{times}` or `{lmodern}`, or `{palatino}` if it's
  installed. Sans fonts: `{lmodern-sans}` or `{helvetica}`. For any other font
  installed on their computer, use `\SetSystemFont{Font Name}`, which needs
  `RESUME_TEX=xelatex` for `build.py` and the XeLaTeX compiler on Overleaf.
- `\SetAccentColor{hex}`, `\SetHeaderAlign{left}`, `\SetPaper{a4}` for
  non-US users, plus sizes and margins via `\setlength` (see
  `styles/classic.tex`).

Show the user the result and ask whether they want something different.

### 7. Verify

- Compile every version file with `pdflatex -interaction=nonstopmode <file>.tex`,
  or `xelatex` if you used `\SetSystemFont`. In each `.log`, look for
  `(1 page` in the "Output written" line (it may wrap across lines). Also look
  for `Overfull \hbox` warnings and for `zsresume Warning` lines, such as a
  font that isn't installed.
- A real resume that runs to two pages gets `\squeeze{0.85}` first, and
  shorter presets only after that.
- **Coverage check:** every bullet from every input resume should appear, word
  for word or as a recorded variant, somewhere in `content/`. List any you
  deliberately left out.
- Search the repo for "Jordan", "Example State", "Acme", "Transit" and
  "Classifier" to make sure no example content is left. The examples in this
  file and the README are fine.

### 8. Report to the user

Summarize:

- which versions you recreated
- the section mapping
- every AI-condensed variant that needs review
- any conflicts you resolved and how
- anything left out

Then explain the everyday workflow: to tailor for a job, run
`python3 build.py --clipboard` with the job description copied, or paste it to
an AI and ask it to tailor using only existing presets.

## Later: tailoring to a job (every AI session)

Follow `CLAUDE.md`: only **reorder, select and trim** existing bullets and
presets. If a posting asks for something that isn't in `content/`, report it
as a gap and don't write it in. New wording goes in as a new variant next to
the old one, and only with the user's approval.
