import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import time

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

class SheetsDB:
    def __init__(self):
        self.client = None
        self.sheet = None
        self.connection_error = None
        self._connect()

    def _connect(self):
        """Connect to Google Sheets using Streamlit secrets."""
        try:
            if "gcp_service_account" not in st.secrets:
                self.connection_error = "Missing 'gcp_service_account' in secrets.toml"
                return

            # Construct credentials from secrets
            # Streamlit secrets dict is not exactly a dict, convert it
            service_account_info = dict(st.secrets["gcp_service_account"])
            
            creds = Credentials.from_service_account_info(
                service_account_info, scopes=SCOPES
            )
            self.client = gspread.authorize(creds)
            
            # Open the sheet
            # We assume the user has created a sheet named "OKR_DB"
            # Or we could config the name
            sheet_name = "OKR_DB"
            try:
                self.sheet = self.client.open(sheet_name).sheet1
                self.connection_error = None # Clear any previous error
            except gspread.SpreadsheetNotFound:
                # Optional: Create if not exists? (Requires Drive write scope, which we added)
                # But safer to ask user to create it.
                self.connection_error = f"Spreadsheet '{sheet_name}' not found. Please create it and share with service account."
                self.sheet = None
                
        except Exception as e:
            self.connection_error = f"Failed to connect: {str(e)}"
            self.client = None

    def get_connection_status(self):
        """Returns (is_connected, error_message)"""
        return (self.sheet is not None, self.connection_error)

    def is_connected(self):
        return self.sheet is not None

    def get_user_data(self, username):
        """Fetch data for a specific user. Returns dict or None."""
        if not self.sheet:
            return None
        
        try:
            # Search for username in Column A
            # Note: In newer gspread, find() returns None if not found (no exception)
            cell = self.sheet.find(username, in_column=1)
            if cell:
                # Data is in Column B (col 2)
                data_str = self.sheet.cell(cell.row, 2).value
                return json.loads(data_str)
            return None
        except Exception as e:
            st.error(f"Error fetching data: {str(e)}")
            return None

    def get_all_rows(self):
        """Fetch all rows from the sheet (for admin view). Returns list of dicts."""
        if not self.sheet:
            return []
        try:
            # Returns list of lists
            records = self.sheet.get_all_records()
            return records
        except Exception as e:
            st.error(f"Error fetching all data: {str(e)}")
            return []

    def save_user_data(self, username, data):
        """Save or update user data."""
        if not self.sheet:
            return False

        try:
            # Ensure headers exist
            headers = self.sheet.row_values(1)
            if not headers:
                self.sheet.insert_row(["username", "data", "timestamp"], 1)
            
            data_str = json.dumps(data)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Search for username in Column A
            cell = self.sheet.find(username, in_column=1)

            if cell:
                # Update existing row
                self.sheet.update_cell(cell.row, 2, data_str)
                self.sheet.update_cell(cell.row, 3, timestamp)
            else:
                # Append new row
                self.sheet.append_row([username, data_str, timestamp])
                
            return True
        except Exception as e:
            st.error(f"Error saving data: {str(e)}")
            return False
