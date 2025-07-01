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
    # Get credentials from environment variables (GitHub secrets)
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
    """Get sales orders from last 30 days"""
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"session_id={session_id}"
    }

    # Last 30 days
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')

    data = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "sale.order",
            "method": "search_read",
            "args": [[
                "&",
                ("create_date", ">=", f"{thirty_days_ago} 00:00:00"),
                ("create_date", "<=", f"{today} 23:59:59")
            ]],
            "kwargs": {
                "fields": [
                    "id", 
                    "create_date",
                    "name",
                    "state",
                    "source_id",
                    "medium_id",
                    "campaign_id",
                    "pricelist_id",
                    "website_id",      
                    "amount_total",
                    "user_id",
                    "partner_id"
                ],
                "order": "create_date desc"
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

def write_to_odoo_sales_test_tab(sheets, sales_orders):
    """Write data to the 'odoo_sales_test' tab"""
    try:
        sheet = sheets.open_by_key(SPREADSHEET_ID)
        
        # Check if 'odoo_sales_test' tab exists, if not create it
        try:
            worksheet = sheet.worksheet('odoo_sales_test')
        except:
            worksheet = sheet.add_worksheet(title='odoo_sales_test', rows=1000, cols=13)
            print("Created new 'odoo_sales_test' worksheet")
        
        # Clear existing data
        worksheet.clear()
        print("Cleared existing data from odoo_sales_test tab")
        
        # Prepare headers
        headers = [
            "Date",
            "Sale Order ID", 
            "Sale Order Name",
            "Status",
            "Customer",
            "Source",
            "Medium",
            "Campaign",
            "Pricelist",
            "Website",
            "Amount",
            "User"
        ]
        
        # Prepare data rows
        rows = [headers]
        for sale in sales_orders:
            rows.append([
                sale.get('create_date', ''),
                sale['id'],
                sale.get('name', ''),
                sale.get('state', ''),
                sale.get('partner_id', ['', ''])[1] if sale.get('partner_id') else '',
                sale.get('source_id', ['', ''])[1] if sale.get('source_id') else '',
                sale.get('medium_id', ['', ''])[1] if sale.get('medium_id') else '',
                sale.get('campaign_id', ['', ''])[1] if sale.get('campaign_id') else '',
                sale.get('pricelist_id', ['', ''])[1] if sale.get('pricelist_id') else '',
                sale.get('website_id', ['', ''])[1] if sale.get('website_id') else '',
                sale.get('amount_total', 0),
                sale.get('user_id', ['', ''])[1] if sale.get('user_id') else ''
            ])
        
        # Write data starting from A1
        worksheet.update(values=rows, range_name="A1")
        print(f"Successfully wrote {len(sales_orders)} sales orders to odoo_sales_test tab")
        
        return True
        
    except Exception as e:
        print(f"Error writing to odoo_sales_test tab: {e}")
        return None

def main():
    print("Starting Odoo sales orders data collection...")
    
    # Authenticate with Odoo
    session_id = authenticate_odoo()
    if not session_id:
        print("Failed to authenticate with Odoo")
        return
    
    print("Authentication successful")
    
    # Get sales orders
    sales_orders = get_sales_orders(session_id)
    
    if sales_orders:
        # Import gspread here
        from google.oauth2.service_account import Credentials
        import gspread
        
        # Authenticate with Google Sheets
        credentials = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        sheets = gspread.authorize(credentials)
        
        print("Writing data to odoo_sales_test tab...")
        success = write_to_odoo_sales_test_tab(sheets, sales_orders)
        if success:
            print("Process completed successfully!")
        else:
            print("Failed to write data to spreadsheet")
    else:
        print("No data to process")

if __name__ == "__main__":
    main()
