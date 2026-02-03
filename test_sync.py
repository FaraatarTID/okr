
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import os

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def test_connection():
    print("Testing Google Sheets Connection...")
    
    # Check secrets manually if possible or use st.secrets if running via streamlit
    # Since we are running via 'python', st.secrets might not work unless we mock it or use secrets.toml directly
    
    secrets_path = "streamlit_app/.streamlit/secrets.toml"
    if not os.path.exists(secrets_path):
        secrets_path = ".streamlit/secrets.toml"
    
    if os.path.exists(secrets_path):
        import toml
        with open(secrets_path, "r") as f:
            secrets = toml.load(f)
            if "gcp_service_account" in secrets:
                print("✅ Found gcp_service_account in secrets.toml")
                try:
                    service_account_info = secrets["gcp_service_account"]
                    creds = Credentials.from_service_account_info(
                        service_account_info, scopes=SCOPES
                    )
                    client = gspread.authorize(creds)
                    print("✅ Authorized successfully")
                    
                    try:
                        SPREADSHEET_NAME = "OKR_DB"
                        sh = client.open(SPREADSHEET_NAME)
                        print(f"✅ Opened spreadsheet '{SPREADSHEET_NAME}' successfully")
                        print(f"URL: {sh.url}")
                    except gspread.SpreadsheetNotFound:
                        print(f"❌ Spreadsheet '{SPREADSHEET_NAME}' NOT FOUND")
                        print("Existing spreadsheets:")
                        for s in client.openall():
                            print(f" - {s.title} ({s.url})")
                    except Exception as e:
                        print(f"❌ Failed to open spreadsheet: {e}")
                except Exception as e:
                    print(f"❌ Authorization failed: {e}")
            else:
                print("❌ gcp_service_account NOT FOUND in secrets.toml")
    else:
        print(f"❌ {secrets_path} NOT FOUND")

if __name__ == "__main__":
    test_connection()
