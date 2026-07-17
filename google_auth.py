import os
import time
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from functools import wraps

SCOPES = [
    '[https://www.googleapis.com/auth/spreadsheets](https://www.googleapis.com/auth/spreadsheets)',
    '[https://www.googleapis.com/auth/drive](https://www.googleapis.com/auth/drive)'
]
SERVICE_ACCOUNT_FILE = 'service_account.json'

def get_google_clients():
    """Authenticate and return Google API clients"""
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"Cannot find authorization file {SERVICE_ACCOUNT_FILE}")
        
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    drive_service = build('drive', 'v3', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    
    return gc, drive_service, sheets_service

def with_retry(max_retries=5, base_delay=2):
    """Google API Anti-crash Retry Mechanism (Exponential Backoff)"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e).lower()
                    # Catch 429 or Quota limit errors
                    if '429' in error_msg or 'quota' in error_msg or 'too many requests' in error_msg:
                        delay = base_delay * (2 ** retries)
                        print(f"   ⏳ Triggered Google API rate limit, waiting {delay} seconds before retrying... ({retries+1}/{max_retries})", flush=True)
                        time.sleep(delay)
                        retries += 1
                    else:
                        raise e # Throw directly for other non-rate-limit errors
            raise Exception("❌ Max retries reached, API request failed.")
        return wrapper
    return decorator
