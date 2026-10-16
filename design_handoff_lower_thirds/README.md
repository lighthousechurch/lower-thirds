# Handoff: Sermon Slides → Lower Thirds Automation

## Overview
Weekly workflow for Lighthouse Church North County. Josh (josh@lighthousechurchnc.org) emails sermon slides as numbered JPGs. Automate: find the email, download the JPGs, convert each into a 1920×1080 transparent PNG lower third (text band at bottom), zip in order, and reply-all on the thread with the zip attached.

## About the Design Files
`Lower Third Converter.dc.html` is an **HTML design reference / working prototype** (browser canvas + Tesseract OCR). It is not production code. Recreate the logic in the target environment (e.g. a Python or Node script run by Claude Code with Gmail access). The rendering rules below are the spec.

## Fidelity
High-fidelity: output PNGs should match the spec pixel for pixel. Reference outputs: `reference/01.png`–`04.png` (made from `reference/Slide1–4.jpeg`).

## Pipeline
1. **Find email**: Gmail search `from:josh@lighthousechurchnc.org has:attachment (filename:jpg OR filename:jpeg)`, newest unreplied thread. Subjects vary ("Sermon Slides", "Sermon Notes for Sunday…", "The Church in Ephesus").
2. **Download** all JPG attachments from that message.
3. **Sort** by the number in the filename, natural order (Slide1, Slide2 … Slide10), not alphabetical.
4. **Sermon title**: parse from body, e.g. "The title is simply The Church of Philadelphia" / "The sermon title is Every Day Faith". Used for slide 1 (series graphic with no readable verse text). If not found, ask the user.
5. **OCR** slides 2..N (see below).
6. **Render** each lower third (see spec).
7. **Output** `01.png`, `02.png`, … zero-padded to at least 2 digits, in slide order; zip as `<title> - lower thirds.zip`.
8. **Reply-all** on the thread's latest message: To/CC preserved (Josh, Febe, Diego/silverbullet_300@yahoo.com, Robert, and others on the original). Corey sends it, so exclude Corey from recipients. Attach zip. Suggested body: "Hey @Febe Garcia and @Diego Duarte, here are the lower-thirds in .png format. Let me know if these work!" **Create as a draft first for review** unless told to auto-send.

## OCR
Tesseract (eng). Preprocess: slides are white text on a blue textured background. Convert each pixel to black if min(R,G,B) > 232, else white, then OCR. Post-process: collapse newlines/whitespace to single spaces, replace `|` with `I`, strip non-printable characters (keep curly quotes ‘ ’ “ ” and — …). **Always show OCR text for human review** — it is correct on the sample but can misread.

## Lower third render spec
- Canvas 1920×1080 RGBA PNG, fully transparent except the band.
- Band: y = 880 to 1080 (200px tall), full width, drawn from `band.png` (1920×200 texture cut from the original lower third: pale-blue concrete with a crack and cloud at the right).
- Text: **Source Serif 4 Bold (700)**, color `#1b2a33`, left aligned at x = 88px, max line width 1920 − 176 = 1744px.
- Vertical placement: block of lines centered on y = 980 (band center). Line height = round(size × 1.04). Baseline of line i = 980 − (n−1)·lh/2 + i·lh + size × 0.33.
- Size logic ("fit" mode, default): start at 58px, step down by 2 to 44 until text wraps to ≤2 lines; else try 50 → 34 for ≤3 lines; else 34px truncated to 4 lines with "...". The pastor/stream team asked that big paragraphs **not be split across slides**, so shrink rather than cut.
- Optional "trunc" mode: 58px, 2 lines max, ending with "..." (word boundary, trailing punctuation trimmed).
- Slide 1: single line, title text.

## Assets
- `band.png` — band texture (derived from `reference/01.png` bottom-right region, mirrored/tiled to fill the left).
- Font: Source Serif 4 (Google Fonts), weight 700.
- `reference/` — sample input slides and expected outputs for validation.

## Context from the email history
- Sep 3: first test, Corey sent 1920×1080 numbered PNGs; stream team confirmed they load into ProPresenter and are triggered there.
- Oct 2: reply "Lower thirds in order – 01.png … " was sent to silverbullet_300@yahoo.com with Josh, Febe, jadencrtv@gmail.com on CC. Follow the same pattern.
- Pending: "Sermon Slides" (Oct 8, The Church of Philadelphia), thread id `1a11ccad0a52c450`, no reply yet.

## Files
- `Lower Third Converter.dc.html` — prototype (UI + render + OCR + zip export)
- `band.png`
- `reference/` — sample slides and outputs
