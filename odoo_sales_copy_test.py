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

def get_sales_orders(session_id):
    """Get sales orders from last 90 days"""
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"session_id={session_id}"
    }

    ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    data = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "sale.order",
            "method": "search_read",
            "args": [[
                ("create_date", ">=", f"{ninety_days_ago} 00:00:00")
            ]],
            "kwargs": {
                "fields": [
                    "id", 
                    "name"
                ],
                "limit": 50
            }
        }
    }

    response = requests.post(ODOO_URL + "/web/dataset/call_kw/sale.order/search_read", data=json.dumps(data), headers=headers)

    if response.status_code == 200:
        result = response.json().get("result", [])
        print(f"API Response successful, found {len(result)} sales orders")
        return result
    else:
        print(f"API Error: {response.status_code}")
        return []

def write_to_sales_test_tab(sheets, sales_orders):
    """Write data to the 'sales_test' tab"""
    try:
        sheet = sheets.open_by_key(SPREADSHEET_ID)
        
        try:
            worksheet = sheet.worksheet('sales_test')
        except:
            worksheet = sheet.add_worksheet(title='sales_test', rows=1000, cols=2)
            print("Created new 'sales_test' worksheet")
        
        worksheet.clear()
        print("Cleared existing data from sales_test tab")
        
        headers = ["ID", "Order Number"]
        
        rows = [headers]
        for order in sales_orders:
            rows.append([
                order.get('id', ''),
                order.get('name', '')
            ])
        
        worksheet.update(values=rows, range_name="A1")
        print(f"Successfully wrote {len(sales_orders)} sales orders to sales_test tab")
        
        return True
        
    except Exception as e:
        print(f"Error writing to sales_test tab: {e}")
        return None

def main():
    print("Starting Odoo sales orders test...")
    
    session_id = authenticate_odoo()
    if not session_id:
        print("Failed to authenticate with Odoo")
        return
    
    print("Authentication successful")
    
    sales_orders = get_sales_orders(session_id)
    
    if sales_orders:
        from google.oauth2.service_account import Credentials
        import gspread
        
        credentials = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        sheets = gspread.authorize(credentials)
        
        print("Writing data to sales_test tab...")
        success = write_to_sales_test_tab(sheets, sales_orders)
        if success:
            print("Process completed successfully!")
        else:
            print("Failed to write data to spreadsheet")
    else:
        print("No sales orders found")

if __name__ == "__main__":
    main()
