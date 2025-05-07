import os
import requests
import json
import gspread
from google.oauth2.service_account import Credentials
import traceback
from datetime import datetime

# Print environment variables for debugging
print("Environment variables:")
print(f"ODOO_URL: {os.environ.get('ODOO_URL')}")
print(f"PRODUCT_SPREADSHEET_ID: {os.environ.get('PRODUCT_SPREADSHEET_ID')}")
print(f"Service account file exists: {os.path.exists('service_account.json')}")

# Define scopes and files
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'service_account.json'
SPREADSHEET_ID = os.environ.get('PRODUCT_SPREADSHEET_ID')
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
            return True, response.cookies
        else:
            print(f"✗ Failed to authenticate to Odoo: {response.text}")
            return False, None
    except Exception as e:
        print(f"✗ Error connecting to Odoo: {e}")
        traceback.print_exc()
        return False, None

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
            worksheet.update_cell(4, 4, f"Test connection successful at {datetime.now()}")
            print(f"✓ Successfully wrote to cell D4")
            
            return True, spreadsheet, value
        except Exception as e:
            print(f"✗ Error accessing worksheet: {e}")
            return False, None, None
            
    except Exception as e:
        print(f"✗ Error connecting to spreadsheet: {e}")
        traceback.print_exc()
        return False, None, None

def fetch_product_variants(session, product_name, spreadsheet):
    """Fetch product variants from Odoo and write to spreadsheet"""
    print(f"\n=== Fetching variants for product: {product_name} ===")
    
    headers = {"Content-Type": "application/json"}
    
    # Search for product template
    search_data = {
        "jsonrpc": "2.0",
        "params": {
            "model": "product.template",
            "method": "search_read",
            "args": [
                [["name", "=", product_name]],
                ["id", "name"]
            ],
            "kwargs": {}
        }
    }
    
    response = session.post(
        f"{ODOO_URL}/web/dataset/call_kw", 
        data=json.dumps(search_data), 
        headers=headers
    )
    
    search_result = response.json()
    if "result" not in search_result or not search_result["result"]:
        print(f"✗ No product template found with name: {product_name}")
        return False
        
    template_id = search_result["result"][0]["id"]
    template_name = search_result["result"][0]["name"]
    print(f"✓ Found product template: {template_name} (ID: {template_id})")
    
    # Try simpler approach - just get basic variant info
    variants_data = {
        "jsonrpc": "2.0",
        "params": {
            "model": "product.product",
            "method": "search_read",
            "args": [
                [["product_tmpl_id", "=", template_id]],
                ["id", "name", "default_code", "lst_price", "standard_price"]  # Removed attribute_value_ids
            ],
            "kwargs": {}
        }
    }
    
    response = session.post(
        f"{ODOO_URL}/web/dataset/call_kw", 
        data=json.dumps(variants_data), 
        headers=headers
    )
    
    variants_result = response.json()
    if "result" not in variants_result:
        print(f"✗ Error fetching variants: {variants_result}")
        return False
        
    variants = variants_result["result"]
    print(f"✓ Found {len(variants)} variants")
    
    # Write to spreadsheet
    if variants:
        # Create or get variants worksheet
        try:
            variants_sheet = spreadsheet.worksheet("variants")
            variants_sheet.clear()  # Clear existing data
        except gspread.exceptions.WorksheetNotFound:
            variants_sheet = spreadsheet.add_worksheet(title="variants", rows=100, cols=10)
        
        # Write headers
        headers = ["ID", "Name", "SKU", "Sales Price", "Cost", "Last Update"]
        variants_sheet.append_row(headers)
        
        # Write variant rows
        for variant in variants:
            row = [
                variant["id"],
                variant["name"],
                variant["default_code"] or "",
                variant["lst_price"],
                variant["standard_price"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]
            variants_sheet.append_row(row)
        
        print(f"✓ Successfully wrote {len(variants)} variants to spreadsheet")
        return True
    else:
        print("✗ No variants found for this product")
        return False

def create_or_get_worksheet(spreadsheet, name):
    """Create a worksheet if it doesn't exist or get it if it does"""
    try:
        return spreadsheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=name, rows=100, cols=20)

def main():
    print("=== Testing Odoo Connection ===")
    odoo_success, cookies = test_odoo_connection()
    
    print("\n=== Testing Google Sheets Connection ===")
    sheets_success, spreadsheet, product_name = test_spreadsheet_connection()
    
    if odoo_success and sheets_success:
        print("\n✓✓✓ All connections successful! The environment is properly set up.")
        
        # Create a session with the cookies from authentication
        session = requests.Session()
        if cookies:
            session.cookies.update(cookies)
            
        # Fetch and process product variants
        if product_name:
            fetch_product_variants(session, product_name, spreadsheet)
        else:
            print("✗ No product name found in cell B1. Please provide a product name.")
    else:
        print("\n✗✗✗ Some connections failed. Please check the logs above for details.")

if __name__ == "__main__":
    main()
