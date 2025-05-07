import os
import requests
import json
import gspread
from google.oauth2.service_account import Credentials
import traceback
import datetime

# --- Configuration from environment variables ---
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '1Cz3oKbwVBZ9R7JhqL5tKRbk-xRtbAknauXYTCarJrro')
SOURCE_WORKSHEET_NAME = 'start'
TARGET_WORKSHEET_NAME = 'vendor fetch'
SERVICE_ACCOUNT_FILE = 'service_account.json'

ODOO_URL = os.environ.get('ODOO_URL', "https://odoo.optimacompanies.com")
DB = os.environ.get('ODOO_DB', "master")
LOGIN = os.environ.get('ODOO_LOGIN', "philipa@optimacompanies.com")
PASSWORD = os.environ.get('ODOO_PASSWORD', "8uj#eck5")

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def authenticate_odoo():
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
        print("Authenticated to Odoo")
        return response.cookies.get('session_id')
    else:
        raise Exception(f"Odoo auth failed: {response.text}")

def get_variants_from_sheet():
    """Read product variants from the source worksheet"""
    try:
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        gc = gspread.authorize(credentials)
        sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SOURCE_WORKSHEET_NAME)
        
        # Get the template name from cell B1
        template_name = sheet.acell('B1').value
        template_id = sheet.acell('B2').value
        
        # Get all data from the sheet
        all_data = sheet.get_all_values()
        
        # Find the headers row (typically row 5)
        header_row = None
        for i, row in enumerate(all_data):
            if row and row[0] == "ID":
                header_row = i
                break
        
        if header_row is None:
            print("Could not find header row in the sheet")
            return [], None, None
            
        headers = all_data[header_row]
        id_col = headers.index("ID")
        sku_col = headers.index("SKU")
        display_name_col = headers.index("Display Name")
        xml_id_col = headers.index("XML ID") if "XML ID" in headers else None
        
        # Get variants data (rows after the header row)
        variants = []
        for i in range(header_row + 1, len(all_data)):
            row = all_data[i]
            if len(row) > max(id_col, sku_col, display_name_col):
                variant_id = row[id_col].strip()
                sku = row[sku_col].strip()
                display_name = row[display_name_col].strip()
                xml_id = row[xml_id_col].strip() if xml_id_col is not None and xml_id_col < len(row) else ""
                
                if variant_id and variant_id.isdigit():  # Check if ID is a valid number
                    variants.append({
                        'id': int(variant_id),
                        'sku': sku,
                        'display_name': display_name,
                        'xml_id': xml_id
                    })
        
        print(f"Found {len(variants)} variants in the sheet")
        return variants, template_name, template_id
    
    except Exception as e:
        print(f"Error reading variants from sheet: {e}")
        traceback.print_exc()
        return [], None, None

def get_supplier_info(session_id, product_ids):
    """Get supplier information for the given product IDs"""
    if not product_ids:
        return []
    
    headers = {"Content-Type": "application/json", "Cookie": f"session_id={session_id}"}
    data = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "product.supplierinfo",
            "method": "search_read",
            "args": [[["product_id", "in", product_ids]]],
            "kwargs": {
                "fields": [
                    "id", "sequence", "partner_id", "product_id", "product_name", 
                    "product_code", "date_start", "date_end", "min_qty",
                    "product_uom", "price", "delay", "purchase_requisition_id",
                    "company_id"
                ]
            }
        }
    }
    
    response = requests.post(f"{ODOO_URL}/web/dataset/call_kw/product.supplierinfo/search_read", 
                           data=json.dumps(data), headers=headers)
    
    if response.status_code == 200:
        results = response.json().get("result", [])
        print(f"Fetched {len(results)} supplier info records")
        return results
    else:
        print(f"Error fetching supplier info: {response.text}")
        return []

def get_external_ids(session_id, model, ids):
    """Get external IDs for a given model and IDs"""
    if not ids:
        return {}
    
    headers = {"Content-Type": "application/json", "Cookie": f"session_id={session_id}"}
    data = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "ir.model.data",
            "method": "search_read",
            "args": [[["model", "=", model], ["res_id", "in", ids]]],
            "kwargs": {
                "fields": ["res_id", "module", "name", "complete_name"]
            }
        }
    }
    
    response = requests.post(f"{ODOO_URL}/web/dataset/call_kw/ir.model.data/search_read", 
                           data=json.dumps(data), headers=headers)
    
    result = {}
    if response.status_code == 200:
        records = response.json().get("result", [])
        print(f"Fetched {len(records)} external IDs for {model}")
        
        for record in records:
            res_id = record.get('res_id')
            if res_id:
                module = record.get('module', '')
                name = record.get('name', '')
                result[res_id] = f"{module}.{name}"
                
    return result

def get_uom_external_ids(session_id):
    """Get all UoM external IDs"""
    headers = {"Content-Type": "application/json", "Cookie": f"session_id={session_id}"}
    data = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "uom.uom",
            "method": "search_read",
            "args": [[]],
            "kwargs": {
                "fields": ["id", "name"]
            }
        }
    }
    
    response = requests.post(f"{ODOO_URL}/web/dataset/call_kw/uom.uom/search_read", 
                           data=json.dumps(data), headers=headers)
    
    uoms = []
    if response.status_code == 200:
        results = response.json().get("result", [])
        uoms = results
        print(f"Fetched {len(results)} UoMs")
    
    # Get external IDs for these UoMs
    uom_ids = [uom['id'] for uom in uoms]
    external_ids = get_external_ids(session_id, "uom.uom", uom_ids)
    
    # Combine UoM info with external IDs
    uom_with_ext_ids = {}
    for uom in uoms:
        uom_id = uom['id']
        ext_id = external_ids.get(uom_id, f"__export__.uom_uom_{uom_id}")
        uom_with_ext_ids[uom_id] = {
            'id': uom_id,
            'name': uom['name'],
            'external_id': ext_id
        }
    
    return uom_with_ext_ids

def format_value(value, field_type="string"):
    if value is False or value is None:
        return ""
        
    if field_type == "date" and value:
        # Format date properly
        try:
            return value
        except:
            return value
    
    if isinstance(value, list) and len(value) >= 2:
        # Handle many2one fields which appear as [id, name]
        return value[1]
    
    return value

def update_vendor_sheet(session_id, template_name, template_id, variants, supplier_info):
    """Update the vendor fetch worksheet with the collected data"""
    try:
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        gc = gspread.authorize(credentials)
        
        # Try to get the worksheet, create if it doesn't exist
        try:
            sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(TARGET_WORKSHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            print(f"Creating new worksheet: {TARGET_WORKSHEET_NAME}")
            spreadsheet = gc.open_by_key(SPREADSHEET_ID)
            sheet = spreadsheet.add_worksheet(title=TARGET_WORKSHEET_NAME, rows=1000, cols=26)
        
        # Clear the worksheet
        sheet.clear()
        
        # Add header information
        sheet.update(values=[
            ["Template Name:", template_name or ""],
            ["Template ID:", template_id or ""],
            ["Vendor Data Fetch Date:", datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        ], range_name='A1:B3')
        
        # Get external IDs for vendors (partners)
        partner_ids = list(set([info['partner_id'][0] for info in supplier_info if isinstance(info.get('partner_id'), list) and info['partner_id']]))
        partner_external_ids = get_external_ids(session_id, "res.partner", partner_ids)
        
        # Get UoM information
        uom_info = get_uom_external_ids(session_id)
        
        # Get supplier record external IDs
        supplier_record_ids = [info['id'] for info in supplier_info]
        supplier_external_ids = get_external_ids(session_id, "product.supplierinfo", supplier_record_ids)
        
        # Create the headers for the supplier info table
        headers = [
            "Supplier Record ID", "Supplier Ext ID", "Sequence", "Vendor ID", "Vendor Name", 
            "Vendor External ID", "Product ID", "Product XML ID", "Product SKU", 
            "Vendor Product Name", "Vendor Product Code", "Start Date", "End Date", 
            "Min Qty", "UoM ID", "UoM Name", "UoM External ID",
            "Price", "Lead Time (days)", "Company ID", 
            # CSV Import Template Columns
            "CSV Import Template"
        ]
        
        # Add headers to the sheet
        sheet.update_cell(5, 1, "Vendor Information")
        sheet.update(values=[headers], range_name=f'A6:U6')
        
        # Create a mapping of product ID to variant info for easy lookup
        variant_map = {v['id']: v for v in variants}
        
        # Add data rows
        rows = []
        for info in supplier_info:
            # Extract product and partner IDs
            product_id = info.get('product_id', [False, ""])
            product_id_num = product_id[0] if isinstance(product_id, list) and product_id else None
            
            partner_id = info.get('partner_id', [False, ""])
            partner_id_num = partner_id[0] if isinstance(partner_id, list) and partner_id else None
            partner_name = partner_id[1] if isinstance(partner_id, list) and len(partner_id) > 1 else ""
            
            # Get variant info
            variant = variant_map.get(product_id_num, {})
            variant_xml_id = variant.get('xml_id', "")
            
            # Get partner external ID
            partner_external_id = partner_external_ids.get(partner_id_num, f"__export__.res_partner_{partner_id_num}")
            
            # Get supplier record external ID
            supplier_record_id = info['id']
            supplier_record_ext_id = supplier_external_ids.get(supplier_record_id, f"__export__.product_supplierinfo_{supplier_record_id}")
            
            # UoM info
            uom_id = info.get('product_uom', [False, ""])
            uom_id_num = uom_id[0] if isinstance(uom_id, list) and uom_id else None
            uom_name = uom_id[1] if isinstance(uom_id, list) and len(uom_id) > 1 else ""
            uom_external_id = uom_info.get(uom_id_num, {}).get('external_id', "") if uom_id_num else ""
            
            # Company info
            company_id = info.get('company_id', [False, ""])
            company_id_num = company_id[0] if isinstance(company_id, list) and company_id else None
            
            # Format date values
            date_start = format_value(info.get('date_start'), "date")
            date_end = format_value(info.get('date_end'), "date")
            
            # Build CSV import template
            product_field = f"{variant_xml_id}" if variant_xml_id else f"{product_id_num}"
            csv_template = f"id,display_name,supplier_name:partner_id/id,supplier_product_name,supplier_product_code,"
            csv_template += f"supplier_min_qty,supplier_price,supplier_delay,supplier_product_uom/id"
            csv_template += f"\n{product_field},\"{variant.get('display_name', '')}\",{partner_external_id},"
            csv_template += f"\"{info.get('product_name', '')}\",\"{info.get('product_code', '')}\","
            csv_template += f"{info.get('min_qty', '1.0')},{info.get('price', '0.0')},{info.get('delay', '0')},"
            csv_template += f"{uom_external_id}"
            
            row = [
                supplier_record_id,  # Supplier Record ID
                supplier_record_ext_id,  # Supplier Ext ID
                info.get('sequence', ""),  # Sequence
                partner_id_num,  # Vendor ID
                partner_name,  # Vendor Name
                partner_external_id,  # Vendor External ID
                product_id_num,  # Product ID
                variant_xml_id,  # Product XML ID
                variant.get('sku', ""),  # Product SKU
                info.get('product_name', ""),  # Vendor Product Name
                info.get('product_code', ""),  # Vendor Product Code
                date_start,  # Start Date
                date_end,  # End Date
                info.get('min_qty', ""),  # Min Qty
                uom_id_num,  # UoM ID
                uom_name,  # UoM Name
                uom_external_id,  # UoM External ID
                info.get('price', ""),  # Price
                info.get('delay', ""),  # Lead Time (days)
                company_id_num,  # Company ID
                csv_template,  # CSV Import Template
            ]
            rows.append(row)
        
        # Sort rows by vendor name, then product
        rows.sort(key=lambda x: (x[4] or "", x[6] or ""))
        
        # Update the sheet with all rows
        if rows:
            sheet.update(values=rows, range_name=f"A7:U{6+len(rows)}")
            
            # Add a formula to count vendors
            sheet.update_cell(4, 1, f"Vendor Count:")
            sheet.update_cell(4, 2, f'=COUNTA(UNIQUE(E7:E{6+len(rows)}))')
        
        # Format the sheet
        sheet.format('A6:U6', {'textFormat': {'bold': True}})
        sheet.format('A5', {'textFormat': {'bold': True}})
        
        # Set the first column width wider for CSV template
        sheet.update_cell(7, 21, "Copy row above for CSV Upload Template for new similar products")
        
        print(f"Vendor fetch sheet updated with {len(rows)} supplier information records")
        
    except Exception as e:
        print(f"Error updating vendor sheet: {e}")
        traceback.print_exc()

def main():
    try:
        print("Starting vendor info fetch script...")
        
        # Get variants from the starting sheet
        variants, template_name, template_id = get_variants_from_sheet()
        
        if not variants:
            print("No variants found in the sheet. Exiting.")
            return
            
        # Authenticate to Odoo
        session_id = authenticate_odoo()
        
        # Get list of product IDs
        product_ids = [variant['id'] for variant in variants]
        
        # Get supplier information
        supplier_info = get_supplier_info(session_id, product_ids)
        
        # Update the vendor sheet
        update_vendor_sheet(session_id, template_name, template_id, variants, supplier_info)
        
        print("Vendor information fetching completed successfully.")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
