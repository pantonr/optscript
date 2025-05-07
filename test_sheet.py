import os
import gspread
from google.oauth2.service_account import Credentials
import traceback
import datetime

# Get environment variables
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
SERVICE_ACCOUNT_FILE = 'service_account.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def main():
    print(f"Starting test with spreadsheet ID: {SPREADSHEET_ID}")
    print(f"Service account file exists: {os.path.exists(SERVICE_ACCOUNT_FILE)}")
    
    try:
        # Authenticate
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        gc = gspread.authorize(credentials)
        print("Successfully authenticated with Google")
        
        # Open the spreadsheet
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        print(f"Successfully opened spreadsheet: {spreadsheet.title}")
        
        # List all worksheets
        worksheets = spreadsheet.worksheets()
        print(f"Available worksheets: {[ws.title for ws in worksheets]}")
        
        # Try to update the first worksheet
        first_sheet = worksheets[0]
        print(f"Updating sheet: {first_sheet.title}")
        
        # Update a cell
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        first_sheet.update_cell(1, 1, f"Test update at {timestamp}")
        print(f"Successfully updated cell A1 with timestamp: {timestamp}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    print(f"Test completed. Success: {success}")
