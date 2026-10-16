#!/usr/bin/env python3
"""One-time Gmail sign-in. Run on your own computer:

  pip install google-auth-oauthlib
  python3 authorize.py client_secret.json

A browser opens; sign in as corey@lighthousechurchnc.org. The printed JSON is
the GMAIL_TOKEN_JSON that gmail_run.py reads.
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], ["https://www.googleapis.com/auth/gmail.modify"])
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
print("\nGMAIL_TOKEN_JSON:\n")
print(creds.to_json())
