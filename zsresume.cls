% ============================================================================
%  zsresume.cls  --  measured single-page resume class
%
%  Every dimension below was measured directly from Apple Pages PDF exports
%  so that output matches that layout baseline-for-baseline.
%
%  You should not need to edit this file day to day.  The only things worth
%  touching are the tuning lengths in the "SPACING DIALS" block -- change one
%  number there and the whole page reflows consistently.
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

\RequirePackage[T1]{fontenc}
\RequirePackage[utf8]{inputenc}
\RequirePackage{mathptmx}      % Nimbus Roman -- metrically identical to Times New Roman
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
\geometry{
  paperwidth=612bp, paperheight=792bp,
  left=36bp, right=36bp,
  top=26.5bp, bottom=28bp,
  headheight=0bp, headsep=0bp, footskip=0bp,
}
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
\newcommand{\zsBody}{\fontsize{11bp}{\zsBodyLead}\selectfont}
\newcommand{\zsOrg}{\fontsize{12bp}{\zsEntryLead}\selectfont\bfseries}
\newcommand{\zsSectionFont}{\fontsize{14bp}{\zsSecLead}\selectfont\bfseries}
\newcommand{\zsNameFont}{\fontsize{20bp}{20bp}\selectfont\bfseries}
\newcommand{\zsContactFont}{\fontsize{10bp}{13.6bp}\selectfont}

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
  {\centering\zsNameFont #1\par}%
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
  {\centering\zsContactFont #1 | #2 | Phone: #3 | Email: #4\par}%
  \vspace{2.4bp}%
}

% ---------------------------------------------------------------------------
%  SECTION HEADER   \section{EDUCATION}
% ---------------------------------------------------------------------------
% The rule under each section header is drawn as a zero-height overlay
% (\smash) so it cannot disturb the baseline grid.
\newlength{\zsRuleThick} \setlength{\zsRuleThick}{1.5bp}
\newlength{\zsRuleDrop}  \setlength{\zsRuleDrop}{5.08bp} % rule centre below baseline
\newlength{\zsRuleLen}   \setlength{\zsRuleLen}{540bp}   % full measured text width

\renewcommand{\section}[1]{%
  \par\vspace{\zsSecBefore}%
  {\zsSectionFont
   \leavevmode\rlap{\raisebox{-\zsRuleDrop}[0pt][0pt]{\rule{\zsRuleLen}{\zsRuleThick}}}%
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
    \llap{\raisebox{-\zsBulletDrop}{\fontsize{13.2bp}{13.2bp}\selectfont\textbullet}%
          \hspace*{\dimexpr\zsBulletIndent-\zsBulletMark-4.62bp\relax}}%
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
