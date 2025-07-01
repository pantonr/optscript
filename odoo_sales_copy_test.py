import requests
import json
from datetime import datetime, timedelta
import os

# Configuration - modified for GitHub Actions
SERVICE_ACCOUNT_FILE = 'service_account.json'
SPREADSHEET_ID = '1nHciwKuK_G2wKd4G5i4Fo1gpMNJoscxaDt-LIGHH2EU'

# Odoo credentials - will use GitHub secrets
ODOO_URL = "https://odoo.optimacompanies.com/"
ODOO_DB = "master"

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets'
]

def authenticate_odoo():
    """Authenticate with Odoo"""
    login = os.environ.get('ODOO_USERNAME')
    password = os.environ.get('ODOO_PASSWORD')
    
    headers = {"Content-Type": "application/json"}
    auth_data = {
        "jsonrpc": "2.0",
        "params": {
            "db": ODOO_DB,
            "login": login,
            "password": password
        }
    }
    
    response = requests.post(ODOO_URL + "/web/session/authenticate", data=json.dumps(auth_data), headers=headers)
    
    if response.status_code == 200 and "result" in response.json():
        return response.cookies.get('session_id')
    else:
        print("Authentication failed")
        return None

def test_all_models(session_id):
    """Test multiple models to see what exists"""
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"session_id={session_id}"
    }

    models_to_test = [
        "sale.order",
        "sale.order.line", 
        "account.move",
        "crm.lead",
        "res.partner"
    ]
    
    results = []
    
    for model in models_to_test:
        print(f"Testing {model}...")
        
        data = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": model,
                "method": "search_read",
                "args": [[]],  # No filters
                "kwargs": {
                    "fields": ["id"],
                    "limit": 5
                }
            }
        }

        response = requests.post(ODOO_URL + f"/web/dataset/call_kw/{model}/search_read", data=json.dumps(data), headers=headers)
        
        if response.status_code == 200:
            result = response.json().get("result", [])
            count = len(result)
            print(f"  {model}: {count} records found")
            results.append([model, count, "SUCCESS"])
        else:
            print(f"  {model}: ERROR {response.status_code}")
            results.append([model, 0, f"ERROR {response.status_code}"])
    
    return results

def write_debug_to_sheet(sheets, results):
    """Write debug results to sheet"""
    try:
        sheet = sheets.open_by_key(SPREADSHEET_ID)
        
        try:
            worksheet = sheet.worksheet('debug_test')
        except:
            worksheet = sheet.add_worksheet(title='debug_test', rows=100, cols=3)
            print("Created new 'debug_test' worksheet")
        
        worksheet.clear()
        
        headers = ["Model", "Record Count", "Status"]
        rows = [headers] + results
        
        worksheet.update(values=rows, range_name="A1")
        print("Debug results written to debug_test tab")
        
    except Exception as e:
        print(f"Error writing debug: {e}")

def main():
    print("Starting Odoo model test...")
    
    session_id = authenticate_odoo()
    if not session_id:
        print("Failed to authenticate with Odoo")
        return
    
    print("Authentication successful")
    
    # Test all models
    results = test_all_models(session_id)
    
    # Always write to sheet, even if empty
    from google.oauth2.service_account import Credentials
    import gspread
    
    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    sheets = gspread.authorize(credentials)
    
    write_debug_to_sheet(sheets, results)
    print("Process completed - check debug_test tab!")

if __name__ == "__main__":
    main()
