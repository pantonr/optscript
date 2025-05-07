import os
import requests
import json
import gspread
from google.oauth2.service_account import Credentials
import traceback

# Print environment variables for debugging
print("Environment variables:")
print(f"ODOO_URL: {os.environ.get('ODOO_URL')}")
print(f"PRODUCT_SPREADSHEET_ID: {os.environ.get('PRODUCT_SPREADSHEET_ID')}")
print(f"Service account file exists: {os.path.exists('service_account.json')}")

# Define scopes and files
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'service_account.json'
SPREADSHEET_ID = os.environ.get('PRODUCT_SPREADSHEET_ID')  # Changed to match workflow env var name
WORKSHEET_NAME = 'start'

ODOO_URL = os.environ.get('ODOO_URL')
DB = os.environ.get('ODOO_DB')
LOGIN = os.environ.get('ODOO_LOGIN')
PASSWORD = os.environ.get('ODOO_PASSWORD')

def test_odoo_connection():
    """Test connection to Odoo"""
    try:
        headers = {"Content-Type": "application/json"}
        auth_data = {
            "jsonrpc": "2.0",
            "params": {
                "db": DB,
                "login": LOGIN,
                "password": PASSWORD
            }
        }
        
        print(f"Connecting to Odoo at: {ODOO_URL}")
        response = requests.post(
            f"{ODOO_URL}/web/session/authenticate", 
            data=json.dumps(auth_data), 
            headers=headers
        )
        
        if response.status_code == 200 and "result" in response.json():
            print("✓ Successfully authenticated to Odoo")
            return True
        else:
            print(f"✗ Failed to authenticate to Odoo: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error connecting to Odoo: {e}")
        traceback.print_exc()
        return False

def test_spreadsheet_connection():
    """Test connection to Google Sheets"""
    try:
        print(f"Connecting to spreadsheet ID: {SPREADSHEET_ID}")
        credentials = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, 
            scopes=SCOPES
        )
        gc = gspread.authorize(credentials)
        
        # Try to open the spreadsheet
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        print(f"✓ Successfully opened spreadsheet: {spreadsheet.title}")
        
        # Try to access the worksheet
        try:
            worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
            print(f"✓ Successfully accessed worksheet: {WORKSHEET_NAME}")
            
            # Read cell B1
            value = worksheet.acell('B1').value
            print(f"✓ Value in cell B1: {value}")
            
            # Write a test value to cell D2
            worksheet.update_cell(4, 4, f"Test connection successful at {__import__('datetime').datetime.now()}")
            print(f"✓ Successfully wrote to cell D4")
            
            return True
        except Exception as e:
            print(f"✗ Error accessing worksheet: {e}")
            return False
            
    except Exception as e:
        print(f"✗ Error connecting to spreadsheet: {e}")
        traceback.print_exc()
        return False

def main():
    print("=== Testing Odoo Connection ===")
    odoo_success = test_odoo_connection()
    
    print("\n=== Testing Google Sheets Connection ===")
    sheets_success = test_spreadsheet_connection()
    
    if odoo_success and sheets_success:
        print("\n✓✓✓ All connections successful! The environment is properly set up.")
    else:
        print("\n✗✗✗ Some connections failed. Please check the logs above for details.")

if __name__ == "__main__":
    main()
