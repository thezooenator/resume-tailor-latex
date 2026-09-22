# Working on this resume

- Still showing the example person (Jordan Lee)? The user wants to set it up
  for themselves: follow PERSONALIZE.md, using the resumes in my_resumes/.
- Formatting (font, sizes, colour, margins, paper) lives in style.tex, never
  in content/. styles/classic.tex lists every setting.
- Content lives in content/*.tex. Version files (example.tex,
  skills_early.tex, autofill.tex) contain no wording — only running orders.
- Presets are built FROM individual bullets. Edit a bullet once;
  never duplicate text.
- content/catalog.json describes every preset for build.py. When a preset is
  added or renamed in content/*.tex, update catalog.json to match.
- When tailoring to a job description: only reorder, select, and
  trim existing bullets. If a posting wants something not in
  content/, tell me it's a gap — don't write a new claim.
- New wording goes in as a NEW variant alongside the old one,
  never overwriting it.
- Real resumes must stay one page. Try \squeeze{0.85} before cutting.
  build.py does this itself: it steps down SQUEEZE_LADDER until
  pdflatex reports one page. Don't hardcode a squeeze value there.
- Build with: pdflatex example.tex
- Dimensions are in bp, not pt.
