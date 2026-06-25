---
name: Template tag formatting
description: Django template tags must never be split across HTML lines — formatters break them.
---
**Rule:** Every `{% %}` tag must open and close on the same line. Multi-line template tags cause `TemplateSyntaxError` at render time.

**Why:** The Django template parser is line-aware. Code formatters (Prettier, Black HTML) sometimes wrap long tags across lines, breaking them silently at format time but crashing at runtime.

**How to apply:** After any auto-format of a template, run: `python3 -c "with open('template.html') as f: [print(i+1,l) for i,l in enumerate(f) if l.count('{%') != l.count('%}')]"` to find mismatched tags. Fix by collapsing onto one line.
