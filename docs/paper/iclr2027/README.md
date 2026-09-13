# REVOKE — ICLR 2027 draft (Overleaf-ready)

Import: Overleaf → New Project → Upload Project → this zip.
Compiler: pdfLaTeX. Main document: `main.tex`. Bibliography: BibTeX with the
ICLR style (`iclr2027_conference.bst`), references in `references.bib`.

Draft conventions
- `\ph{...}` — amber chip: a number or phrase still to be filled from the full evaluation.
- `\pilot`   — green tag: a value measured on the five-episode long-tier pilot.
- Uncomment `\finaldrafttrue` in the preamble to strip both markers; uncomment
  `\iclrfinalcopy` only for the camera-ready (authors are hidden until then).
- Three BibTeX entries are stubs marked TODO (StateMemBench, MemEvolve, EvolveLab):
  fill from the design note's reference list before submission.

Files from the official template (github.com/ICLR/Master-Template, iclr2027):
iclr2027_conference.sty, iclr2027_conference.bst, math_commands.tex, fancyhdr.sty, natbib.sty.
Source of every measured number: github.com/Dextergao14/REVOKE, data/long/eval_runs and scripts/long_report.py.
