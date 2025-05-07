import os
import requests
import json
import gspread
from google.oauth2.service_account import Credentials
import traceback
import string
from datetime import datetime

# Environment variables
ODOO_URL = os.environ.get('ODOO_URL')
DB = os.environ.get('ODOO_DB')
LOGIN = os.environ.get('ODOO_LOGIN')
PASSWORD = os.environ.get('ODOO_PASSWORD')
SPREADSHEET_ID = os.environ.get('PRODUCT_SPREADSHEET_ID')
WORKSHEET_NAME = 'start'

# Define scopes and files
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'service_account.json'

def authenticate_odoo():
    """Authenticate to Odoo and return session_id"""
    headers = {"Content-Type": "application/json"}
    auth_data = {
        "jsonrpc": "2.0",
        "params": {
            "db": DB,
            "login": LOGIN,
            "password": PASSWORD
        }
    }
    response = requests.post(f"{ODOO_URL}/web/session/authenticate", data=json.dumps(auth_data), headers=headers)
    if response.status_code == 200 and "result" in response.json():
        print("✓ Authenticated to Odoo")
        return response.cookies
    else:
        print(f"✗ Odoo auth failed: {response.text}")
        return None

def get_product_name():
    """Get product name from spreadsheet cell B1"""
    credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc = gspread.authorize(credentials)
    sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    product_name = sheet.acell('B1').value
    print(f"Read product name from sheet: {product_name}")
    return product_name

def get_template_by_name(session, product_name):
    """Find product template by name"""
    headers = {"Content-Type": "application/json"}
    data = {
        "jsonrpc": "2.0",
        "params": {
            "model": "product.template",
            "method": "search_read",
            "args": [
                [["name", "=", product_name]],
                ["id", "name", "product_variant_ids"]
            ],
            "kwargs": {}
        }
    }
    response = session.post(f"{ODOO_URL}/web/dataset/call_kw", data=json.dumps(data), headers=headers)
    result = response.json().get("result", [])
    if result:
        print(f"✓ Found template: {result[0]['name']} with ID: {result[0]['id']}")
        return result[0]
    print(f"✗ No template found for: {product_name}")
    return None

def get_variants(session, template_id):
    """Get all variant data for a template"""
    headers = {"Content-Type": "application/json"}
    data = {
        "jsonrpc": "2.0",
        "params": {
            "model": "product.product",
            "method": "search_read",
            "args": [
                [["product_tmpl_id", "=", template_id]],
                # Include all the fields you need
                [
                    "id", "name", "display_name", "default_code", "product_template_variant_value_ids",
                    "detailed_type", "lst_price", "standard_price", "weight", "sales_count",
                    "length", "width", "height", "freight_class", "package_type", "ship_method",
                    "product_tag_ids", "route_ids", "categ_id", "x_studio_bin_location",
                    "sale_ok", "purchase_ok", "allow_out_of_stock_order"
                ]
            ],
            "kwargs": {}
        }
    }
    response = session.post(f"{ODOO_URL}/web/dataset/call_kw", data=json.dumps(data), headers=headers)
    variants = response.json().get("result", [])
    print(f"✓ Found {len(variants)} variants")
    return variants

def get_attribute_values(session, attribute_ids):
    """Get attribute value details"""
    if not attribute_ids:
        return {}
    headers = {"Content-Type": "application/json"}
    data = {
        "jsonrpc": "2.0",
        "params": {
            "model": "product.template.attribute.value",
            "method": "search_read",
            "args": [
                [["id", "in", attribute_ids]],
                ["id", "name", "display_name", "attribute_id"]
            ],
            "kwargs": {}
        }
    }
    response = session.post(f"{ODOO_URL}/web/dataset/call_kw", data=json.dumps(data), headers=headers)
    results = response.json().get("result", [])
    print(f"✓ Found {len(results)} attribute values")
    
    # Convert to dictionary for easy lookup
    values = {}
    for val in results:
        values[val['id']] = val
    return values

def get_product_tags(session, tag_ids):
    """Get product tag details"""
    if not tag_ids:
        return {}
    headers = {"Content-Type": "application/json"}
    data = {
        "jsonrpc": "2.0",
        "params": {
            "model": "product.tag",
            "method": "search_read",
            "args": [
                [["id", "in", tag_ids]],
                ["id", "name"]
            ],
            "kwargs": {}
        }
    }
    response = session.post(f"{ODOO_URL}/web/dataset/call_kw", data=json.dumps(data), headers=headers)
    results = response.json().get("result", [])
    
    # Convert to dictionary
    tags = {}
    for tag in results:
        tags[tag['id']] = tag['name']
    return tags

def column_letter(n):
    """Convert column number to letter (1 -> A, 27 -> AA)"""
    result = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = string.ascii_uppercase[remainder] + result
    return result or "A"

def update_sheet(template, variants, attributes):
    """Update the spreadsheet with product data"""
    credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc = gspread.authorize(credentials)
    sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    
    # Update template info in first rows
    if template:
        sheet.update(values=[
            ["Template Name:", template['name']],
            ["Template ID:", template['id']],
            ["Variant Count:", len(variants)]
        ], range_name='A1:B3')
    
        # Clear data area
        sheet.batch_clear(["A5:ZZ1000"])
        
        if variants:
            # Collect all attribute names
            attr_sets = {}
            for variant in variants:
                for attr_id in variant.get('product_template_variant_value_ids', []):
                    if attr_id in attributes:
                        attr = attributes[attr_id]
                        attr_name = attr.get('attribute_id')[1] if attr.get('attribute_id') else "Unknown"
                        attr_sets[attr_name] = True
            
            # Create headers
            sorted_attrs = sorted(attr_sets.keys())
            headers = [
                "ID", "Display Name", "SKU", "Price", "Cost",
                "Weight", "Length", "Width", "Height",
                "Can Be Sold", "Can Be Purchased", "Allow Out of Stock"
            ] + sorted_attrs
            
            last_col = column_letter(len(headers))
            sheet.update(values=[headers], range_name=f'A5:{last_col}5')
            
            # Prepare rows
            rows = []
            for variant in variants:
                # Create variant attributes dict
                variant_attrs = {}
                for attr_id in variant.get('product_template_variant_value_ids', []):
                    if attr_id in attributes:
                        attr = attributes[attr_id]
                        if attr.get('attribute_id'):
                            attr_name = attr.get('attribute_id')[1]
                            attr_val = attr.get('name', '').split(':')[-1].strip()
                            variant_attrs[attr_name] = attr_val
                
                # Format boolean values
                sale_ok = "Yes" if variant.get('sale_ok') else "No"
                purchase_ok = "Yes" if variant.get('purchase_ok') else "No"
                allow_out_of_stock = "Yes" if variant.get('allow_out_of_stock_order') else "No"
                
                # Create row
                row = [
                    variant.get('id', ''),
                    variant.get('display_name', ''),
                    variant.get('default_code', ''),
                    variant.get('lst_price', 0),
                    variant.get('standard_price', 0),
                    variant.get('weight', 0),
                    variant.get('length', 0),
                    variant.get('width', 0),
                    variant.get('height', 0),
                    sale_ok,
                    purchase_ok,
                    allow_out_of_stock
                ]
                
                # Add attribute values
                for attr_name in sorted_attrs:
                    row.append(variant_attrs.get(attr_name, ''))
                
                rows.append(row)
            
            # Write all rows
            if rows:
                print(f"Writing {len(rows)} rows to spreadsheet")
                sheet.update(values=rows, range_name=f'A6:{last_col}{5+len(rows)}')
        
        print("✓ Spreadsheet updated successfully")
    else:
        sheet.update_cell(1, 1, "No product template found")

def main():
    print("Fetching product variants...")
    
    try:
        # Get product name
        product_name = get_product_name()
        
        if not product_name:
            print("✗ No product name found in cell B1")
            return
        
        # Authenticate to Odoo
        cookies = authenticate_odoo()
        if not cookies:
            print("✗ Failed to authenticate to Odoo")
            return
        
        # Create session with cookies
        session = requests.Session()
        session.cookies.update(cookies)
        
        # Get product template
        template = get_template_by_name(session, product_name)
        if not template:
            print(f"✗ Product template not found: {product_name}")
            update_sheet(None, [], {})
            return
        
        # Get all variants
        variants = get_variants(session, template['id'])
        
        # Collect all attribute IDs
        attr_ids = []
        for variant in variants:
            attr_ids.extend(variant.get('product_template_variant_value_ids', []))
        
        # Get attribute details
        attr_values = get_attribute_values(session, attr_ids)
        
        # Update spreadsheet
        update_sheet(template, variants, attr_values)
        
    except Exception as e:
        print(f"✗ Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
