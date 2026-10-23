#!/usr/bin/env python3
"""Find Josh's latest sermon slides email, build the lower thirds, and leave a
reply-all draft on the thread with the zip attached.

Needs GMAIL_TOKEN_JSON (from authorize.py) in the environment.

Usage:
  gmail_run.py [--thread THREAD_ID] [--dry-run] [--force]
  gmail_run.py --check     # only report whether there is new work (run=true/false)
"""
import argparse
import base64
import io
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from email.message import EmailMessage
from email.utils import getaddresses
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

import lower_thirds

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
SEARCH = ("from:josh@lighthousechurchnc.org has:attachment "
          "(filename:jpg OR filename:jpeg) (sermon OR slides) newer_than:14d")
# Josh has used both "Slide1.jpeg" and "1.jpg".
SLIDE_NAME = re.compile(r"^(?:slide\s*)?\d+\.jpe?g$", re.I)
DONE_LABEL = "Lower thirds/Drafted"
BODY = ("Hey @Febe Garcia and @Diego Duarte, here are the lower-thirds in .png format. "
        "Let me know if these work!")


def gmail():
    creds = Credentials.from_authorized_user_info(json.loads(os.environ["GMAIL_TOKEN_JSON"]), SCOPES)
    if not creds.valid:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def headers(msg):
    return {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}


def parts(payload):
    yield payload
    for p in payload.get("parts", []) or []:
        yield from parts(p)


def plain_body(msg):
    for p in parts(msg["payload"]):
        if p.get("mimeType") == "text/plain" and p.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", "replace")
    return ""


def find_title(body, attachment_names, subject):
    """Sermon title from the email body, else the .pptx name, else None."""
    text = " ".join(body.split())
    m = re.search(r"title(?: of (?:the|my|this|sunday's) (?:sermon|message))? is (?:simply |called )?[\"“]?(.+?)[\"”]?(?:\.(?:\s|$)|$|\s--)",
                  text, re.I)
    if m:
        return m.group(1).strip()
    for n in attachment_names:
        if n.lower().endswith((".pptx", ".key", ".pdf")):
            return Path(n).stem
    return None


def label_id(svc, create=False):
    for lab in svc.users().labels().list(userId="me").execute().get("labels", []):
        if lab["name"] == DONE_LABEL:
            return lab["id"]
    if create:
        return svc.users().labels().create(userId="me", body={"name": DONE_LABEL}).execute()["id"]
    return None


def done_this_week(svc):
    """True if a slides email from this week (since Monday, Pacific) was already drafted."""
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    monday = (now - timedelta(days=now.weekday())).strftime("%Y/%m/%d")
    q = f'label:"{DONE_LABEL}" after:{monday}'
    return bool(svc.users().threads().list(userId="me", q=q, maxResults=1).execute().get("threads"))


def slides_message(thread):
    """Josh's newest message in the thread with Slide1.jpeg, Slide2.jpeg ... attached."""
    for m in reversed(thread["messages"]):
        if "josh@" not in headers(m).get("from", "").lower():
            continue
        if sum(bool(SLIDE_NAME.match(p.get("filename") or "")) for p in parts(m["payload"])) >= 2:
            return m
    return None


def pick_thread(svc, me, thread_id=None, force=False):
    ids = [thread_id] if thread_id else [
        t["id"] for t in svc.users().threads().list(userId="me", q=SEARCH, maxResults=5).execute().get("threads", [])]
    done = label_id(svc)
    for tid in ids:  # newest first
        thread = svc.users().threads().get(userId="me", id=tid, format="full").execute()
        msgs = thread["messages"]
        if not slides_message(thread):
            print(f"thread {tid}: no SlideN.jpeg attachments, skipping")
            continue
        if force:
            return thread
        if done and any(done in m.get("labelIds", []) for m in msgs):
            print(f"thread {tid}: already drafted, skipping")
            continue
        slides_idx = msgs.index(slides_message(thread))
        if any(me in headers(m).get("from", "").lower() for m in msgs[slides_idx + 1:]):
            print(f"thread {tid}: already replied, skipping")
            continue
        return thread
    return None


def download_slides(svc, msg, dest):
    files, names = [], []
    for p in parts(msg["payload"]):
        name = p.get("filename") or ""
        if not name:
            continue
        names.append(name)
        if not SLIDE_NAME.match(name):
            continue
        att = svc.users().messages().attachments().get(
            userId="me", messageId=msg["id"], id=p["body"]["attachmentId"]).execute()
        path = Path(dest) / name
        path.write_bytes(base64.urlsafe_b64decode(att["data"]))
        files.append(path)
    return sorted(files, key=lower_thirds.natural_key), names


def reply_all(svc, me, thread, zip_path):
    last = thread["messages"][-1]
    h = headers(last)
    def addrs(*names):
        return [a for _, a in getaddresses([h.get(n, "") for n in names]) if a and a.lower() != me]
    to = list(dict.fromkeys(addrs("reply-to") or addrs("from")))
    to += [a for a in addrs("to") if a not in to]
    cc = [a for a in dict.fromkeys(addrs("cc")) if a not in to]

    em = EmailMessage()
    em["To"] = ", ".join(to)
    if cc:
        em["Cc"] = ", ".join(cc)
    subject = h.get("subject", "")
    em["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    em["In-Reply-To"] = h.get("message-id", "")
    em["References"] = f'{h.get("references", "")} {h.get("message-id", "")}'.strip()
    em.set_content(BODY)
    em.add_attachment(zip_path.read_bytes(), maintype="application", subtype="zip", filename=zip_path.name)

    media = MediaIoBaseUpload(io.BytesIO(em.as_bytes()), mimetype="message/rfc822", resumable=True)
    draft = svc.users().drafts().create(
        userId="me", body={"message": {"threadId": thread["id"]}}, media_body=media).execute()
    return draft, to, cc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thread", help="use this thread id instead of searching")
    ap.add_argument("--dry-run", action="store_true", help="build the zip but don't create a draft")
    ap.add_argument("--force", action="store_true", help="ignore the already-drafted/replied checks")
    ap.add_argument("--check", action="store_true", help="only report whether there is new work")
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    svc = gmail()
    me = svc.users().getProfile(userId="me").execute()["emailAddress"].lower()
    if args.check:
        if not args.force and not args.thread and done_this_week(svc):
            print("Already drafted this week's lower thirds.")
            thread = None
        else:
            thread = pick_thread(svc, me, args.thread, args.force)
        found = "true" if thread else "false"
        print(f"run={found}")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"run={found}\n")
        return
    thread = pick_thread(svc, me, args.thread, args.force)
    if not thread:
        print("No new sermon slides email.")
        return

    msg = slides_message(thread)
    subject = headers(msg).get("subject", "")
    print(f"Thread {thread['id']}: {subject}")

    with tempfile.TemporaryDirectory() as tmp:
        slides, names = download_slides(svc, msg, tmp)
        title = find_title(plain_body(msg), names, subject)
        if not title:
            raise RuntimeError(f"Couldn't find the sermon title in '{subject}'; rerun with the thread id after checking.")
        print(f"Title: {title} ({len(slides)} slides)")
        texts = [title] + [lower_thirds.ocr(p) for p in slides[1:]]

    out = Path(args.out)
    zip_path = lower_thirds.build(texts, out, f"{title} - lower thirds.zip")
    (out / "texts.json").write_text(json.dumps(texts, ensure_ascii=False, indent=2))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(f"## {title}\n\n| PNG | Text |\n|---|---|\n")
            for i, t in enumerate(texts, 1):
                f.write(f"| {i:02d} | {t.replace('|', '/')} |\n")

    if args.dry_run:
        print("Dry run: no draft created.")
        return
    draft, to, cc = reply_all(svc, me, thread, zip_path)
    svc.users().threads().modify(userId="me", id=thread["id"],
                                 body={"addLabelIds": [label_id(svc, create=True)]}).execute()
    print(f"Draft {draft['id']} created. To: {', '.join(to)}  Cc: {', '.join(cc)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(tb, file=sys.stderr)
        if os.environ.get("GITHUB_ACTIONS"):
            # Show the real error in the run's annotations, not just "exit code 1".
            msg = f"{type(e).__name__}: {e}".replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print(f"::error title=Lower thirds failed::{msg}")
            if os.environ.get("GITHUB_STEP_SUMMARY"):
                with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
                    f.write(f"## Failed\n\n```\n{tb}\n```\n")
        sys.exit(1)
