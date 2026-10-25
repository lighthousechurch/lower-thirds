# Lower thirds

Turns Josh's weekly sermon slide JPGs into 1920×1080 transparent PNG lower thirds for ProPresenter.

## Setup

```sh
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng wamerican
pip install -r requirements.txt
```

## Automatic run (GitHub Actions)

`.github/workflows/lower-thirds.yml` runs Wed–Sat at 10am and 7pm Pacific. Each run checks Gmail for Josh's
slides email; once a draft has been made for this week, the remaining runs stop early. The draft is a reply-all
on Josh's thread with the zip attached — review it in Gmail and hit send. Each run's page shows the slide text
for checking, and the PNGs are downloadable as a run artifact.

Run it by hand from the Actions tab ("Run workflow"), optionally with a thread id, dry run, or force.

One-time setup: create a Desktop OAuth client (Gmail API enabled, Internal consent screen) in Google Cloud,
run `python3 authorize.py client_secret_….json` on your computer, and save the printed JSON as the repo
secret `GMAIL_TOKEN_JSON`.

## Manual run

1. Download all JPG attachments from Josh's "Sermon Slides" email into `slides/`.
2. Read the text off the slides:
   ```sh
   python3 lower_thirds.py ocr slides/*.jpeg > texts.json
   ```
3. Edit `texts.json`: put the sermon title (from the email body) in slide 1's `text`, and fix any OCR misreads.
4. Render and zip:
   ```sh
   python3 lower_thirds.py render texts.json out --zip "The Church of Philadelphia - lower thirds.zip"
   ```
5. Reply-all on Josh's thread (leave Corey off) with the zip attached:
   "Hey @Febe Garcia and @Diego Duarte, here are the lower-thirds in .png format. Let me know if these work!"

## Render rules

- Band texture `design_handoff_lower_thirds/band.png` at y = 880–1080.
- Text: Source Serif 4 Bold, `#1b2a33`, left at x = 88, 58px, **max 2 lines**, cut off with "..." at a word boundary.
- Slide 1 (title): single line at 79px, matching `reference/01.png`.
- Output files are `01.png`, `02.png`, … in slide order (Slide1, Slide2 … Slide10 — numeric, not alphabetical).

`design_handoff_lower_thirds/` holds the original Claude Design handoff (spec, browser prototype, and reference slides/outputs).
The font is Source Serif 4 (SIL Open Font License), 36pt optical-size static instance.
