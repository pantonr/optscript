import os
import requests
import json
import gspread
from google.oauth2.service_account import Credentials
import traceback
import string

# --- Configuration from environment variables ---
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
WORKSHEET_NAME = 'start'
SERVICE_ACCOUNT_FILE = 'service_account.json'

ODOO_URL = os.environ.get('ODOO_URL')
DB = os.environ.get('ODOO_DB')
LOGIN = os.environ.get('ODOO_LOGIN')
PASSWORD = os.environ.get('ODOO_PASSWORD')

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def authenticate_odoo():
    headers = {"Content-Type": "application/json"}
    auth_data = {
        "jsonrpc": "2.0"	
        "params": {
            "db": DB	
            "login": LOGIN	
            "password": PASSWORD
        }
    }
    response = requests.post(f"{ODOO_URL}/web/session/authenticate"	 data=json.dumps(auth_data)	 headers=headers)
    if response.status_code == 200 and "result" in response.json():
        print("Authenticated to Odoo")
        return response.cookies.get('session_id')
    else:
        raise Exception(f"Odoo auth failed: {response.text}")

def get_product_name_from_sheet():
    """Read the product name from cell B1 in the spreadsheet"""
    try:
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE	 scopes=SCOPES)
        gc = gspread.authorize(credentials)
        sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
        
        # Get value from B1
        product_name = sheet.acell('B1').value
        
        if not product_name:
            print("No product name found in cell B1	 using default: GR-GW")
            return "GR-GW"
        
        print(f"Found product name in sheet: {product_name}")
        return product_name.strip()
    
    except Exception as e:
        print(f"Error reading product name from sheet: {e}")
        print("Using default product name: GR-GW")
        return "GR-GW"

def get_template_by_name(session_id	 name):
    headers = {"Content-Type": "application/json"	 "Cookie": f"session_id={session_id}"}
    data = {
        "jsonrpc": "2.0"	
        "method": "call"	
        "params": {
            "model": "product.template"	
            "method": "search_read"	
            "args": [[["name"	 "="	 name]]]	
            "kwargs": {
                "fields": ["id"	 "name"	 "product_variant_ids"]	
                "limit": 1
            }
        }
    }
    response = requests.post(f"{ODOO_URL}/web/dataset/call_kw/product.template/search_read"	 data=json.dumps(data)	 headers=headers)
    if response.status_code == 200:
        result = response.json().get("result"	 [])
        if result:
            print(f"Found template: {result[0]['name']} with ID: {result[0]['id']}")
            return result[0]
    print(f"No template found for: {name}")
    return None

def get_variants_by_template(session_id	 template_id):
    # First get basic variant info
    headers = {"Content-Type": "application/json"	 "Cookie": f"session_id={session_id}"}
    data = {
        "jsonrpc": "2.0"	
        "method": "call"	
        "params": {
            "model": "product.product"	
            "method": "search_read"	
            "args": [[["product_tmpl_id"	 "="	 template_id]]]	
            "kwargs": {
                "fields": [
                    # Basic fields
                    "id"	 "display_name"	 "default_code"	 "product_template_variant_value_ids"	
                    
                    # Fields from the HTML sections
                    "x_studio_child_title"	 "x_studio_subject_matter_1"	 
                    "x_studio_classification"	 "website_meta_description"	
                    "x_studio_google_merchant_title"	 "x_studio_google_highlights"	
                    "detailed_type"	 
                    "x_studio_bin_location"	
                    "lst_price"	 
                    "standard_price"	
                    "categ_id"	
                    "product_tag_ids"	
                    
                    # Additional boolean fields
                    "sale_ok"	
                    "purchase_ok"	
                    "allow_out_of_stock_order"	
                    
                    # Logistics fields
                    "route_ids"	
                    "weight"	
                    "length"	
                    "width"	
                    "height"	
                    "freight_class"	
                    "package_type"	
                    "ship_method"	
                    
                    # Sales stats
                    "sales_count"
                ]
            }
        }
    }
    response = requests.post(f"{ODOO_URL}/web/dataset/call_kw/product.product/search_read"	 data=json.dumps(data)	 headers=headers)
    if response.status_code == 200:
        variants = response.json().get("result"	 [])
        print(f"Fetched {len(variants)} variants via search_read")
        
        # Debug: print field names found in the first variant
        if variants:
            print(f"Available fields in first variant: {'	 '.join(variants[0].keys())}")
            
        return variants
    print(f"Error fetching variants: {response.text}")
    return []

def get_template_attribute_values(session_id	 variant_ids):
    """Get attribute value details - these are the tags you see in the UI"""
    if not variant_ids:
        return {}
        
    headers = {"Content-Type": "application/json"	 "Cookie": f"session_id={session_id}"}
    data = {
        "jsonrpc": "2.0"	
        "method": "call"	
        "params": {
            "model": "product.template.attribute.value"	
            "method": "search_read"	
            "args": [[["id"	 "in"	 variant_ids]]]	
            "kwargs": {
                "fields": ["id"	 "name"	 "display_name"	 "attribute_id"	 "product_attribute_value_id"]
            }
        }
    }
    
    response = requests.post(f"{ODOO_URL}/web/dataset/call_kw/product.template.attribute.value/search_read"	 
                           data=json.dumps(data)	 headers=headers)
    
    values = {}
    if response.status_code == 200:
        results = response.json().get("result"	 [])
        print(f"Fetched {len(results)} template attribute values")
        
        for val in results:
            values[val['id']] = val
    else:
        print(f"Error fetching template attribute values: {response.text}")
    
    return values

def get_xml_ids(session_id	 model	 ids):
    """Get the external (XML) IDs for records"""
    if not ids:
        return {}
        
    headers = {"Content-Type": "application/json"	 "Cookie": f"session_id={session_id}"}
    data = {
        "jsonrpc": "2.0"	
        "method": "call"	
        "params": {
            "model": "ir.model.data"	
            "method": "search_read"	
            "args": [[["model"	 "="	 model]	 ["res_id"	 "in"	 ids]]]	
            "kwargs": {
                "fields": ["res_id"	 "complete_name"]
            }
        }
    }
    
    response = requests.post(f"{ODOO_URL}/web/dataset/call_kw/ir.model.data/search_read"	 
                           data=json.dumps(data)	 headers=headers)
    
    xml_ids = {}
    if response.status_code == 200:
        results = response.json().get("result"	 [])
        print(f"Fetched {len(results)} XML IDs")
        
        for val in results:
            xml_ids[val['res_id']] = val.get('complete_name'	 '')
    else:
        print(f"Error fetching XML IDs: {response.text}")
    
    return xml_ids

def get_product_tags(session_id	 tag_ids):
    """Get product tag names"""
    if not tag_ids:
        return {}
    
    headers = {"Content-Type": "application/json"	 "Cookie": f"session_id={session_id}"}
    data = {
        "jsonrpc": "2.0"	
        "method": "call"	
        "params": {
            "model": "product.tag"	
            "method": "search_read"	
            "args": [[["id"	 "in"	 tag_ids]]]	
            "kwargs": {
                "fields": ["id"	 "name"]
            }
        }
    }
    
    response = requests.post(f"{ODOO_URL}/web/dataset/call_kw/product.tag/search_read"	 
                           data=json.dumps(data)	 headers=headers)
    
    tags = {}
    if response.status_code == 200:
        results = response.json().get("result"	 [])
        print(f"Fetched {len(results)} product tags")
        
        for tag in results:
            tags[tag['id']] = tag.get('name'	 '')
    else:
        print(f"Error fetching product tags: {response.text}")
    
    return tags

def get_routes(session_id	 route_ids):
    """Get route names"""
    if not route_ids:
        return {}
    
    headers = {"Content-Type": "application/json"	 "Cookie": f"session_id={session_id}"}
    data = {
        "jsonrpc": "2.0"	
        "method": "call"	
        "params": {
            "model": "stock.route"	
            "method": "search_read"	
            "args": [[["id"	 "in"	 route_ids]]]	
            "kwargs": {
                "fields": ["id"	 "name"]
            }
        }
    }
    
    response = requests.post(f"{ODOO_URL}/web/dataset/call_kw/stock.route/search_read"	 
                           data=json.dumps(data)	 headers=headers)
    
    routes = {}
    if response.status_code == 200:
        results = response.json().get("result"	 [])
        print(f"Fetched {len(results)} routes")
        
        for route in results:
            routes[route['id']] = route.get('name'	 '')
    else:
        print(f"Error fetching routes: {response.text}")
    
    return routes

def enrich_variants_with_attributes(session_id	 variants):
    """Add attribute values and related data to each variant"""
    if not variants:
        return variants
        
    # Collect all template attribute value IDs
    all_template_attr_value_ids = set()
    all_product_tag_ids = set()
    all_categ_ids = set()
    all_route_ids = set()
    
    for variant in variants:
        attr_ids = variant.get('product_template_variant_value_ids'	 [])
        all_template_attr_value_ids.update(attr_ids)
        
        # Collect tag IDs
        tag_ids = variant.get('product_tag_ids'	 [])
        all_product_tag_ids.update(tag_ids)
        
        # Collect route IDs
        route_ids = variant.get('route_ids'	 [])
        all_route_ids.update(route_ids)
        
        # Collect category IDs
        if variant.get('categ_id') and isinstance(variant['categ_id']	 list) and variant['categ_id']:
            all_categ_ids.add(variant['categ_id'][0])
    
    # Get details for all attribute values
    template_attr_values = get_template_attribute_values(session_id	 list(all_template_attr_value_ids))
    
    # Get XML IDs for variants
    variant_ids = [v['id'] for v in variants]
    xml_ids = get_xml_ids(session_id	 "product.product"	 variant_ids)
    
    # Get product tags
    product_tags = get_product_tags(session_id	 list(all_product_tag_ids))
    
    # Get routes
    routes = get_routes(session_id	 list(all_route_ids))
    
    # Add attribute info and other related data to each variant
    for variant in variants:
        # Add XML ID
        variant['xml_id'] = xml_ids.get(variant['id']	 '')
        
        # Format product type
        if variant.get('detailed_type'):
            type_mapping = {'consu': 'Consumable'	 'service': 'Service'	 'product': 'Storable Product'}
            variant['product_type'] = type_mapping.get(variant['detailed_type']	 variant['detailed_type'])
        
        # Format price and cost as float numbers
        if 'lst_price' in variant:
            variant['lst_price'] = float(variant['lst_price'])
            
        if 'standard_price' in variant:
            variant['standard_price'] = float(variant['standard_price'])
        
        # Format freight dimensions
        for dim in ['length'	 'width'	 'height'	 'weight']:
            if dim in variant and variant[dim]:
                variant[dim] = float(variant[dim])
        
        # Format package type
        if variant.get('package_type'):
            package_type = variant['package_type']
            if package_type == '"2"':
                variant['package_type_name'] = "Box"
            elif package_type == '"12"':
                variant['package_type_name'] = "Pallet"
            else:
                variant['package_type_name'] = package_type
        
        # Format ship method
        if variant.get('ship_method'):
            ship_method = variant['ship_method']
            if ship_method == '"parcel"':
                variant['ship_method_name'] = "Parcel"
            elif ship_method == '"freight"':
                variant['ship_method_name'] = "Freight"
            else:
                variant['ship_method_name'] = ship_method
        
        # Add product tag names
        variant['tag_names'] = []
        for tag_id in variant.get('product_tag_ids'	 []):
            if tag_id in product_tags:
                variant['tag_names'].append(product_tags[tag_id])
        
        # Add route names
        variant['route_names'] = []
        for route_id in variant.get('route_ids'	 []):
            if route_id in routes:
                variant['route_names'].append(routes[route_id])
        
        # Add variant attributes
        variant_attributes = {}
        for attr_id in variant.get('product_template_variant_value_ids'	 []):
            if attr_id in template_attr_values:
                attr_value = template_attr_values[attr_id]
                
                # Get attribute name and value
                if attr_value.get('display_name'):
                    # Format is typically "Attribute: Value"
                    parts = attr_value['display_name'].split(': '	 1)
                    if len(parts) == 2:
                        attr_name = parts[0]
                        attr_value = parts[1]
                        variant_attributes[attr_name] = attr_value
        
        variant['attributes'] = variant_attributes
    
    return variants

def column_letter(n):
    """Convert column number to letter reference (e.g. 1->A	 27->AA)"""
    result = ""
    while n > 0:
        n	 remainder = divmod(n - 1	 26)
        result = string.ascii_uppercase[remainder] + result
    return result if result else "A"

def update_sheet(template	 variants):
    try:
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE	 scopes=SCOPES)
        gc = gspread.authorize(credentials)
        sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
        
        # Keep existing header row but update the values
        if template:
            sheet.update(values=[
                ["Template Name:"	 template['name']]	
                ["Template ID:"	 template['id']]	
                ["Variant Count:"	 len(variants)]  # Use actual count as an integer
            ]	 range_name='A1:B3')
        else:
            sheet.update(values=[["Template not found"]]	 range_name='A1')
            return

        # Clear the data area (from row 5 down)
        sheet.batch_clear(["A5:ZZ1000"])

        if variants:
            # Collect all attributes to create columns
            all_attributes = set()
            for variant in variants:
                for attr_name in variant.get('attributes'	 {}).keys():
                    all_attributes.add(attr_name)
            
            # Create sorted list of attribute names
            sorted_attrs = sorted(list(all_attributes))
            
            # Create headers - include base fields and attributes
            headers = [
                "ID"	 "XML ID"	 "Display Name"	 "SKU"	 
                "Product Type"	 "Bin Location"	 "List Price"	 "Cost"	
                "Can be Sold"	 "Can be Purchased"	 "Allow Out of Stock"	
                "Routes"	 "Weight"	 "Length"	 "Width"	 "Height"	
                "Freight Class"	 "Package Type"	 "Ship Method"	
                "Units Sold"	 "Child Title"	 "Subject Matter"	 "Classification"	
                "Meta Description"	 "Google Merchant Title"	 "Google Highlights"	
                "Product Tags"
            ] + sorted_attrs
            
            # Get the last column letter
            last_col = column_letter(len(headers))
            print(f"Using column range A5:{last_col}5 for headers")
            
            # Update the sheet with headers
            sheet.update(values=[headers]	 range_name=f'A5:{last_col}5')
            
            # Create rows for each variant
            rows = []
            for v in variants:
                # Format classification value - it might be stored as a JSON string
                classification = v.get('x_studio_classification'	 '')
                if classification and classification.startswith('"') and classification.endswith('"'):
                    classification = classification.strip('"')
                
                # Format tags as comma-separated list
                tags = "	 ".join(v.get('tag_names'	 []))
                routes = "	 ".join(v.get('route_names'	 []))
                
                # Format boolean values
                sale_ok = "Yes" if v.get('sale_ok') else "No"
                purchase_ok = "Yes" if v.get('purchase_ok') else "No"
                allow_out_of_stock = "Yes" if v.get('allow_out_of_stock_order') else "No"
                
                # Basic information
                row = [
                    v["id"]	
                    v.get("xml_id"	 "")	
                    v["display_name"]	
                    v.get("default_code"	 "")	
                    v.get("product_type"	 "")	
                    v.get("x_studio_bin_location"	 "")	
                    v.get("lst_price"	 "")	
                    v.get("standard_price"	 "")	
                    sale_ok	
                    purchase_ok	
                    allow_out_of_stock	
                    routes	
                    v.get("weight"	 "")	
                    v.get("length"	 "")	
                    v.get("width"	 "")	
                    v.get("height"	 "")	
                    v.get("freight_class"	 "")	
                    v.get("package_type_name"	 "")	
                    v.get("ship_method_name"	 "")	
                    v.get("sales_count"	 0)	
                    v.get("x_studio_child_title"	 "")	
                    v.get("x_studio_subject_matter_1"	 "")	
                    classification	
                    v.get("website_meta_description"	 "")	
                    v.get("x_studio_google_merchant_title"	 "")	
                    v.get("x_studio_google_highlights"	 "")	
                    tags
                ]
                
                # Add attribute values in the same order as headers
                for attr_name in sorted_attrs:
                    row.append(v.get('attributes'	 {}).get(attr_name	 ""))
                    
                rows.append(row)
            
            # Update the sheet with all rows
            if rows:
                print(f"Writing {len(rows)} rows x {len(headers)} columns to sheet")
                sheet.update(values=rows	 range_name=f"A6:{last_col}{5+len(rows)}")
            
        else:
            sheet.update_cell(5	 1	 "No variants found.")

        print("Sheet updated successfully.")

    except Exception as e:
        print(f"Sheet update error: {e}")
        traceback.print_exc()

def main():
    try:
        print("Starting fetch.py script...")
        
        # Get product name from sheet
        product_name = get_product_name_from_sheet()
        
        session_id = authenticate_odoo()
        template = get_template_by_name(session_id	 product_name)
        
        if template:
            # Get variants
            variants = get_variants_by_template(session_id	 template['id'])
            
            # Enrich variants with attribute details and related data
            variants = enrich_variants_with_attributes(session_id	 variants)
            
            # Update the sheet
            update_sheet(template	 variants)
        else:
            update_sheet(None	 [])
            
        print("Script completed successfully.")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
