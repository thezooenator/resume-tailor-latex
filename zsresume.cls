% ============================================================================
%  zsresume.cls  --  measured single-page resume class
%
%  Every dimension below was measured directly from Apple Pages PDF exports
%  so that output matches that layout baseline-for-baseline.
%
%  You should not need to edit this file.  To change the look -- font, sizes,
%  margins, colour, bullets, header alignment, paper size -- edit style.tex,
%  which this class reads if it exists.  Ready-made looks live in styles/.
%  Every setting defaults to the measured layout, so with no style.tex the
%  output is unchanged.
% ============================================================================
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{zsresume}[2026/08/14 single-page resume]

% ---------------------------------------------------------------------------
%  CLASS OPTION:  [autofill]
%
%  \documentclass{zsresume}            -> the real resume (measured layout)
%  \documentclass[autofill]{zsresume}  -> plain layout for job-site parsers
%
%  Both read the SAME content files.  Only the layout commands change, so
%  editing a bullet updates the real resume and the autofill version together.
% ---------------------------------------------------------------------------
\newif\ifzsAutofill \zsAutofillfalse
\DeclareOption{autofill}{\zsAutofilltrue}
\ProcessOptions\relax

\LoadClass[letterpaper,11pt]{article}

% pdfLaTeX needs font encodings set up; XeLaTeX/LuaLaTeX use fontspec instead,
% which is what lets \SetSystemFont use any font installed on your computer.
\RequirePackage{iftex}
\iftutex
  \RequirePackage{fontspec}
\else
  \RequirePackage[T1]{fontenc}
  \RequirePackage[utf8]{inputenc}
\fi
\RequirePackage{xcolor}
\RequirePackage{geometry}
\RequirePackage{ragged2e}
\RequirePackage{calc}
\RequirePackage[hidelinks]{hyperref}

% ---------------------------------------------------------------------------
%  PAGE GEOMETRY   (measured: left margin 36pt, right text edge 576pt)
% ---------------------------------------------------------------------------
% NOTE: all dimensions are given in "bp" (big points, 1/72 inch), which is the
% unit Pages and PDF use.  LaTeX's default "pt" is 1/72.27 inch -- using it here
% would shrink the whole page by 0.37% and change where lines wrap.
% The margins are lengths so style.tex can change them; \geometry is applied
% after style.tex has been read (see "APPLY STYLE" below).
\newlength{\zsMarginLeft}   \setlength{\zsMarginLeft}{36bp}
\newlength{\zsMarginRight}  \setlength{\zsMarginRight}{36bp}
\newlength{\zsMarginTop}    \setlength{\zsMarginTop}{26.5bp}
\newlength{\zsMarginBottom} \setlength{\zsMarginBottom}{28bp}
\def\zsPaper{paperwidth=612bp, paperheight=792bp}   % US Letter
\pagestyle{empty}

% ---------------------------------------------------------------------------
%  SPACING DIALS  -- measured baseline-to-baseline advances, in points
% ---------------------------------------------------------------------------
\newlength{\zsBodyLead}     \setlength{\zsBodyLead}{12.0bp} % bullet line -> bullet line
\newlength{\zsEntryLead}    \setlength{\zsEntryLead}{13.7bp}% leading of an entry header line
\newlength{\zsEntryBefore}  \setlength{\zsEntryBefore}{5.1bp}  % extra space above an entry
\newlength{\zsEntryAfter}   \setlength{\zsEntryAfter}{1.7bp}   % entry header -> first bullet
\newlength{\zsSecBefore}    \setlength{\zsSecBefore}{7.1bp}    % extra space above a section rule
\newlength{\zsSecAfter}     \setlength{\zsSecAfter}{0.2bp}     % section header -> first entry
\newlength{\zsSecLead}      \setlength{\zsSecLead}{16.1bp}     % leading of a section header line
\newlength{\zsSkillBefore}  \setlength{\zsSkillBefore}{2.8bp}  % skills line -> skills line
\newlength{\zsBulletIndent} \setlength{\zsBulletIndent}{36bp}  % bullet text indent from margin
\newlength{\zsBulletMark}   \setlength{\zsBulletMark}{18bp}    % bullet glyph indent from margin
\newlength{\zsBulletDrop}   \setlength{\zsBulletDrop}{1.5bp}   % bullet glyph sits below baseline

% ---------------------------------------------------------------------------
%  DENSITY DIAL
%
%  \squeeze{0.8} scales every *discretionary* gap (the space around entries,
%  sections and skills lines) to 80%, without touching the leading inside a
%  bullet.  Use it to claw back a few lines when a version runs long, instead
%  of deleting content.  1.0 = identical to the original Pages layout.
%  Values between 0.6 and 1.0 stay comfortable; below 0.5 it looks cramped.
% ---------------------------------------------------------------------------
\newcommand{\squeeze}[1]{%
  \setlength{\zsEntryBefore}{#1\zsEntryBefore}%
  \setlength{\zsEntryAfter}{#1\zsEntryAfter}%
  \setlength{\zsSecBefore}{#1\zsSecBefore}%
  \setlength{\zsSkillBefore}{#1\zsSkillBefore}%
}

% ---------------------------------------------------------------------------
%  TEXT HELPERS
% ---------------------------------------------------------------------------
\newcommand{\sm}{\raisebox{0.17ex}{$\scriptstyle\sim$}}  % the ~ in "~2,500"
\newcommand{\arr}{\raisebox{0.1ex}{$\scriptstyle\rightarrow$}}                          % the arrow in "greedy->minimax"
\newcommand{\x}{$\times$}                                 % the x in "5x5"
\newcommand{\degsym}{$^{\circ}$}                          % the degree sign in "360 deg"

% ---------------------------------------------------------------------------
%  FONT SIZES  (measured)
% ---------------------------------------------------------------------------
% Each size pairs with a leading (line-to-line distance) in SPACING DIALS
% above; if you change a size, change its leading by about the same ratio.
\newlength{\zsBodySize}     \setlength{\zsBodySize}{11bp}     % bullets, dates, skills
\newlength{\zsOrgSize}      \setlength{\zsOrgSize}{12bp}      % organisation names
\newlength{\zsSectionSize}  \setlength{\zsSectionSize}{14bp}  % section headings
\newlength{\zsNameSize}     \setlength{\zsNameSize}{20bp}     % your name
\newlength{\zsContactSize}  \setlength{\zsContactSize}{10bp}  % contact line
\newlength{\zsContactLead}  \setlength{\zsContactLead}{13.6bp}

\newcommand{\zsBody}{\fontsize{\zsBodySize}{\zsBodyLead}\selectfont}
\newcommand{\zsOrg}{\fontsize{\zsOrgSize}{\zsEntryLead}\selectfont\bfseries}
\newcommand{\zsSectionFont}{\fontsize{\zsSectionSize}{\zsSecLead}\selectfont\bfseries\color{zsAccent}}
\newcommand{\zsNameFont}{\fontsize{\zsNameSize}{\zsNameSize}\selectfont\bfseries\color{zsAccent}}
\newcommand{\zsContactFont}{\fontsize{\zsContactSize}{\zsContactLead}\selectfont}

% ---------------------------------------------------------------------------
%  STYLE HOOKS  -- the commands style.tex uses.  Defaults = measured layout.
% ---------------------------------------------------------------------------
% \SetFont{times}  -- a pdfLaTeX font, loaded after style.tex:
%   times (default) . lmodern . lmodern-sans   -- in every TeX install
%   palatino . helvetica . bookman . newcentury -- in full TeX Live, MacTeX
%     and Overleaf; on BasicTeX run  sudo tlmgr install <package>  first
%   none -- load your own font package in style.tex with \RequirePackage
% A font that is not installed falls back to times with a warning naming
% the package to install, rather than stopping the build.
\def\zsFontName{times}
\newcommand{\SetFont}[1]{\def\zsFontName{#1}}
% \zs@font{name}{marker file}{tlmgr package}{code that loads it}
% The marker is a .fd file that only exists once the font itself is
% installed; an empty marker means "always available".
\newcommand{\zs@font}[4]{%
  \@namedef{zsFontTest@#1}{#2}\@namedef{zsFontPkg@#1}{#3}\@namedef{zsFont@#1}{#4}}
\zs@font{times}{t1utm.fd}{times}{\RequirePackage{mathptmx}}  % Nimbus Roman = Times New Roman widths
\zs@font{lmodern}{}{lm}{\RequirePackage{lmodern}}
\zs@font{lmodern-sans}{}{lm}{\RequirePackage{lmodern}\renewcommand{\familydefault}{\sfdefault}}
\zs@font{palatino}{t1upl.fd}{palatino}{\RequirePackage{mathpazo}}
\zs@font{helvetica}{t1uhv.fd}{helvetic}{\RequirePackage[scaled=0.92]{helvet}\renewcommand{\familydefault}{\sfdefault}}
\zs@font{bookman}{t1ubk.fd}{bookman}{\RequirePackage{bookman}}
\zs@font{newcentury}{t1unc.fd}{ncntrsbk}{\RequirePackage{newcent}}
\zs@font{none}{}{}{}

% Load font #1, falling back to times (and times to lmodern) if missing.
\newcommand{\zs@loadfont}[1]{%
  \@ifundefined{zsFont@#1}{%
    \ClassWarningNoLine{zsresume}{Unknown font `#1'; using times}%
    \zs@loadfont{times}%
  }{%
    \edef\zs@marker{\@nameuse{zsFontTest@#1}}%
    \ifx\zs@marker\@empty
      \@nameuse{zsFont@#1}%
    \else
      \IfFileExists{\zs@marker}{\@nameuse{zsFont@#1}}{%
        \edef\zs@pkg{\@nameuse{zsFontPkg@#1}}%
        \ClassWarningNoLine{zsresume}{Font `#1' is not installed
          (sudo tlmgr install \zs@pkg); falling back}%
        \def\zs@tmp{#1}\def\zs@times{times}%
        \ifx\zs@tmp\zs@times\zs@loadfont{lmodern}\else\zs@loadfont{times}\fi}%
    \fi}}

% \SetSystemFont{Garamond} -- any font installed on your computer.  Needs the
% XeLaTeX or LuaLaTeX compiler (build.py: RESUME_TEX=xelatex); under pdfLaTeX
% it is ignored with a warning and \SetFont applies instead.
\def\zsSystemFont{}
\newcommand{\SetSystemFont}[1]{\def\zsSystemFont{#1}}

% \SetAccentColor{1F3A93} -- hex colour for your name, headings and rules.
\definecolor{zsAccent}{HTML}{000000}
\newcommand{\SetAccentColor}[1]{\definecolor{zsAccent}{HTML}{#1}}

% \SetBullet{\textbullet} -- the bullet glyph: try \textendash, $\circ$,
% \textasteriskcentered, or \raisebox{0.3ex}{\scalebox{0.6}{$\blacksquare$}}.
% \SetBulletSize{13.2bp} scales it.
\newcommand{\zsBulletGlyph}{\textbullet}
\newcommand{\SetBullet}[1]{\renewcommand{\zsBulletGlyph}{#1}}
\newlength{\zsBulletSize} \setlength{\zsBulletSize}{13.2bp}
\newcommand{\SetBulletSize}[1]{\setlength{\zsBulletSize}{#1}}

% \SetHeaderAlign{center} or {left} -- name and contact line alignment.
\newcommand{\zsHeaderAlign}{\centering}
\newcommand{\SetHeaderAlign}[1]{%
  \def\zs@tmp{#1}\def\zs@left{left}%
  \ifx\zs@tmp\zs@left\renewcommand{\zsHeaderAlign}{\raggedright}%
  \else\renewcommand{\zsHeaderAlign}{\centering}\fi}

% \SetContactSeparator{ | } -- what goes between contact fields.
\newcommand{\zsSep}{ | }
\newcommand{\SetContactSeparator}[1]{\renewcommand{\zsSep}{#1}}

% \SetPaper{letter} or {a4}.
\newcommand{\SetPaper}[1]{%
  \def\zs@tmp{#1}\def\zs@afour{a4}%
  \ifx\zs@tmp\zs@afour\def\zsPaper{a4paper}%
  \else\def\zsPaper{paperwidth=612bp, paperheight=792bp}\fi}

% Ragged right, no hyphenation -- Pages never hyphenates, so neither do we.
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\hyphenpenalty=10000
\exhyphenpenalty=10000
\tolerance=9999
\emergencystretch=3em
\raggedbottom

% ---------------------------------------------------------------------------
%  HEADER BLOCK
% ---------------------------------------------------------------------------
% \name{...}
\newcommand{\name}[1]{%
  {\zsHeaderAlign\zsNameFont #1\par}%
}
% Optional contact fields.  Both are set in \Header and both are ignored by
% the real resume -- they exist only to give autofill mode more to hand a
% parser.  Setting neither leaves the header exactly as it was.
%   \linkedin{https://...}      -- own labelled line, printed as a full URL
%   \phoneplain{555-010-0199}   -- parser-friendly phone; falls back to #3
\newcommand{\zsLinkedIn}{}
\newcommand{\zsPhonePlain}{}
\newcommand{\linkedin}[1]{\renewcommand{\zsLinkedIn}{#1}}
\newcommand{\phoneplain}[1]{\renewcommand{\zsPhonePlain}{#1}}

% \contactinfo{street}{city, state zip}{phone}{email}
% Given as separate fields so autofill mode can put each on its own line --
% which it does, in the \ifzsAutofill block near the end of this file.
\newcommand{\contactinfo}[4]{%
  {\zsHeaderAlign\zsContactFont #1\zsSep #2\zsSep Phone: #3\zsSep Email: #4\par}%
  \vspace{2.4bp}%
}

% ---------------------------------------------------------------------------
%  SECTION HEADER   \section{EDUCATION}
% ---------------------------------------------------------------------------
% The rule under each section header is drawn as a zero-height overlay
% (\smash) so it cannot disturb the baseline grid.
\newlength{\zsRuleThick} \setlength{\zsRuleThick}{1.5bp}
\newlength{\zsRuleDrop}  \setlength{\zsRuleDrop}{5.08bp} % rule centre below baseline
\newlength{\zsRuleLen}   % full text width, set once the margins are known

\renewcommand{\section}[1]{%
  \par\vspace{\zsSecBefore}%
  {\zsSectionFont
   \leavevmode\rlap{\raisebox{-\zsRuleDrop}[0pt][0pt]{\color{zsAccent}\rule{\zsRuleLen}{\zsRuleThick}}}%
   #1\par}%
  \vspace{\zsSecAfter}%
  \zsEntryfalse
}

% ---------------------------------------------------------------------------
%  ENTRY HEADER
%
%  \entry{Organization}{detail (set in italic)}{Location | Dates}
%
%  The third argument is flush right.  In the Pages original it was pushed
%  right with literal spaces, which is why the right edge wobbled by a few
%  points between entries; \hfill makes it exact.
% ---------------------------------------------------------------------------
\newif\ifzsEntry \zsEntryfalse

\newcommand{\entry}[3]{%
  \par\vspace{\zsEntryBefore}%
  {\zsOrg #1\normalfont
   \ifx\relax#2\relax\else\hspace{5bp}{\zsBody\itshape #2}\fi
   \hfill{\zsBody #3}\par}%
  \vspace{\zsEntryAfter}%
  \zsEntrytrue
}

% Two-argument convenience: organization + right-hand side only.
\newcommand{\entrytwo}[2]{\entry{#1}{\relax}{#2}}

% ---------------------------------------------------------------------------
%  BULLET LIST
%
%  \begin{bullets} \item ... \end{bullets}
%
%  Implemented by hand rather than with itemize so the vertical rhythm is
%  exactly \zsBodyLead with no list padding of any kind.
% ---------------------------------------------------------------------------
\newenvironment{bullets}{%
  \par\zsBody
  \begingroup
  \RaggedRight                                  % must come first: it resets \leftskip
  \setlength{\leftskip}{\zsBulletIndent}%
  \def\item{%
    \par\noindent
    % The glyph's left edge sits \zsBulletMark from the margin, whatever
    % glyph \SetBullet chose.
    \llap{\makebox[\dimexpr\zsBulletIndent-\zsBulletMark\relax][l]{%
          \raisebox{-\zsBulletDrop}{\fontsize{\zsBulletSize}{\zsBulletSize}\selectfont\zsBulletGlyph}}}%
    \ignorespaces
  }%
}{%
  \par
  \endgroup
}

% ---------------------------------------------------------------------------
%  SKILLS LINES   \skill{Languages}{Python, C/C++, ...}
% ---------------------------------------------------------------------------
\newcommand{\skill}[2]{%
  \par\vspace{\zsSkillBefore}%
  {\zsOrg #1:{\normalfont\zsBody\ #2}\par}%
}

% The first skills line sits at entry distance from the section header;
% subsequent lines are tighter.  \begin{skills} handles the difference.
\newenvironment{skills}{%
  \par\vspace{\dimexpr\zsEntryBefore-\zsSkillBefore\relax}%
}{%
  \par
}

% ===========================================================================
%  APPLY STYLE
%
%  style.tex (next to your .tex files) may change anything above using the
%  \Set... commands or \setlength.  It is read here, then the font and page
%  geometry are applied from whatever it chose.
% ===========================================================================
\InputIfFileExists{style.tex}{}{}

\iftutex
  \ifx\zsSystemFont\empty
    \zs@loadfont{\zsFontName}%
  \else
    \setmainfont{\zsSystemFont}%
  \fi
\else
  \ifx\zsSystemFont\empty\else
    \ClassWarningNoLine{zsresume}{\string\SetSystemFont\space needs XeLaTeX or
      LuaLaTeX; using \string\SetFont{\zsFontName} instead}%
  \fi
  \zs@loadfont{\zsFontName}%
\fi

\expandafter\geometry\expandafter{\zsPaper}
\geometry{
  left=\zsMarginLeft, right=\zsMarginRight,
  top=\zsMarginTop, bottom=\zsMarginBottom,
  headheight=0bp, headsep=0bp, footskip=0bp,
}
\AtBeginDocument{\setlength{\zsRuleLen}{\textwidth}}

% ===========================================================================
%  AUTOFILL MODE
%
%  Job-site resume parsers read a PDF's raw text stream.  Three things in the
%  real layout confuse them, so all three are undone here:
%
%   * the flush-right dates -- the wide gap reads as a column break, so the
%     parser thinks "Springfield, ST | June 2025" belongs to a different field.
%     Here the location and dates run inline after a comma.
%   * the bullet glyphs -- they are drawn outside the text flow with \llap,
%     which can scramble reading order.  Here they are ordinary characters.
%   * the section rules and mixed font sizes, which some parsers treat as
%     structural boundaries.
%
%  Content is untouched.  Length is not constrained -- two pages is fine.
% ===========================================================================
\ifzsAutofill

  \geometry{left=54bp, right=54bp, top=54bp, bottom=54bp}

  \setlength{\zsBodyLead}{13.2bp}
  \setlength{\zsEntryLead}{13.2bp}
  \setlength{\zsEntryBefore}{9bp}
  \setlength{\zsEntryAfter}{1bp}
  \setlength{\zsSecBefore}{13bp}
  \setlength{\zsSecAfter}{3bp}
  \setlength{\zsBulletIndent}{0bp}

  \renewcommand{\zsOrg}{\fontsize{11bp}{\zsEntryLead}\selectfont\bfseries}
  \renewcommand{\zsSectionFont}{\fontsize{11bp}{\zsBodyLead}\selectfont\bfseries}
  \renewcommand{\zsNameFont}{\fontsize{14bp}{16bp}\selectfont\bfseries}
  \renewcommand{\zsContactFont}{\fontsize{11bp}{13.2bp}\selectfont}

  % Left-aligned header, one item per line: parsers pick up name, phone and
  % email far more reliably than from a single centred pipe-separated run.
  %
  % Each line also carries an explicit label.  A bare "(555) 010-0199" on its
  % own line is ambiguous to a parser -- a "Phone:" prefix is the strongest
  % signal there is -- and \phoneplain drops the parentheses, which are the
  % part parsers most often mangle.  The LinkedIn line is printed as a full
  % https:// URL because that is what URL detectors match on.
  \renewcommand{\name}[1]{{\zsNameFont #1\par}}
  \renewcommand{\contactinfo}[4]{%
    {\zsContactFont
     #1, #2\par
     Phone: \ifx\zsPhonePlain\empty #3\else\zsPhonePlain\fi\par
     Email: #4\par
     \ifx\zsLinkedIn\empty\else
       LinkedIn: \href{\zsLinkedIn}{\zsLinkedIn}\par
     \fi
    }\vspace{4bp}}

  % Plain heading, no rule.
  \renewcommand{\section}[1]{%
    \par\vspace{\zsSecBefore}{\zsSectionFont #1\par}\vspace{\zsSecAfter}}

  % Organisation, role, location and dates as one comma-separated sentence.
  \renewcommand{\entry}[3]{%
    \par\vspace{\zsEntryBefore}%
    {\zsOrg #1\normalfont
     \ifx\relax#2\relax\else{\zsBody\ \textemdash\ #2}\fi
     {\zsBody\ifx\relax#3\relax\else, #3\fi}\par}%
    \vspace{\zsEntryAfter}}

  % Hyphen bullets inside the text flow, with a hanging indent for readability.
  \renewenvironment{bullets}{%
    \par\zsBody
    \begingroup
    \RaggedRight
    \setlength{\leftskip}{12bp}%
    \def\item{\par\noindent\hspace*{-12bp}\hbox to 12bp{-\hfil}\ignorespaces}%
  }{\par\endgroup}

  \renewcommand{\skill}[2]{%
    \par\vspace{2bp}{\zsOrg #1:{\normalfont\zsBody\ #2}\par}}

  \renewenvironment{skills}{\par}{\par}

\fi

\endinput
