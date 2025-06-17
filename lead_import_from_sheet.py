import requests
import json
import re
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import os

# Google Sheets Configuration
SERVICE_ACCOUNT_FILE = 'service_account.json'
SPREADSHEET_ID = '1GB1uBtCM58cER-Dnf3M6K7MLCZKpvTl7USLu6ns3hB0'
WORKSHEET_NAME = 'Form responses'
PROCESSING_QUEUE_NAME = 'processing_queue'

# Odoo TEST credentials
odoo_url = os.environ.get('ODOO_URL', 'https://qa-odoo.apps.optimacompanies.com/')
db = os.environ.get('ODOO_DB', 'prod-restore-20250409')
login = os.environ.get('ODOO_LOGIN')
password = os.environ.get('ODOO_PASSWORD')

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]

def authenticate_google_sheets():
    """Authenticate with Google Sheets"""
    try:
        credentials = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        gc = gspread.authorize(credentials)
        return gc
    except Exception as e:
        print(f"Failed to authenticate with Google Sheets: {e}")
        return None

def authenticate_odoo(url, db, login, password):
    """Authenticate with Odoo"""
    headers = {"Content-Type": "application/json"}
    auth_data = {
        "jsonrpc": "2.0",
        "params": {
            "db": db,
            "login": login,
            "password": password
        }
    }
    response = requests.post(url + "/web/session/authenticate", data=json.dumps(auth_data), headers=headers)
    
    if response.status_code == 200 and "result" in response.json():
        print(f"✅ Successfully authenticated with Odoo TEST environment: {url}")
        return response.cookies.get('session_id')
    else:
        print(f"❌ Failed to authenticate with Odoo TEST environment. Status Code: {response.status_code}")
        raise ValueError("Odoo authentication failed")

def check_processing_queue(gc):
    """Check for pending leads in processing queue"""
    try:
        sheet = gc.open_by_key(SPREADSHEET_ID)
        
        # Try to get processing queue sheet
        try:
            processing_sheet = sheet.worksheet(PROCESSING_QUEUE_NAME)
        except:
            print("No processing queue found")
            return []
        
        all_values = processing_sheet.get_all_values()
        if len(all_values) <= 1:  # Only headers or empty
            print("No pending leads in processing queue")
            return []
        
        headers = all_values[0]
        pending_leads = []
        
        for i, row in enumerate(all_values[1:], start=2):  # Start from row 2
            if len(row) >= 4 and row[3] == 'PENDING':
                pending_leads.append({
                    'row': i,
                    'timestamp': row[0],
                    'name': row[1],
                    'email': row[2],
                    'status': row[3]
                })
        
        print(f"Found {len(pending_leads)} pending leads in processing queue")
        return pending_leads
        
    except Exception as e:
        print(f"Error checking processing queue: {e}")
        return []

def mark_lead_processed(gc, row_number, status='PROCESSED'):
    """Mark a lead as processed in the queue"""
    try:
        sheet = gc.open_by_key(SPREADSHEET_ID)
        processing_sheet = sheet.worksheet(PROCESSING_QUEUE_NAME)
        processing_sheet.update_cell(row_number, 4, status)  # Status column
        processing_sheet.update_cell(row_number, 1, datetime.now().isoformat())  # Update timestamp
    except Exception as e:
        print(f"Error marking lead as processed: {e}")

def get_lead_from_form_responses(gc, lead_name, lead_email):
    """Find full lead data from form responses"""
    try:
        sheet = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sheet.worksheet(WORKSHEET_NAME)
        
        all_values = worksheet.get_all_values()
        headers = all_values[0]
        
        # Look for matching lead
        for row in all_values[1:]:
            if len(row) >= len(headers):
                # Check if this matches our lead
                row_first_name = row[1] if len(row) > 1 else ''
                row_last_name = row[2] if len(row) > 2 else ''
                row_email = row[4] if len(row) > 4 else ''
                
                full_name = f"{row_first_name} {row_last_name}".strip()
                
                if (full_name == lead_name or row_email == lead_email) and row_email:
                    # Map to our expected field names
                    form_data = {}
                    for i, header in enumerate(headers):
                        form_data[header] = row[i] if i < len(row) else ''
                    
                    return {
                        'submission_date': form_data.get('Submission Date', ''),
                        'first_name': form_data.get('Name - First Name', ''),
                        'last_name': form_data.get('Name - Last Name', ''),
                        'phone': form_data.get('Phone Number', ''),
                        'email': form_data.get('Email Address', ''),
                        'company': form_data.get('Your Company', ''),
                        'industry': form_data.get('Industry', ''),
                        'whiteboard_type': form_data.get('Whiteboard Type', ''),
                        'size': form_data.get('Approximate Size', ''),
                        'quantity': form_data.get('Quantity', ''),
                        'description': form_data.get('Description', ''),
                        'submission_id': form_data.get('Submission ID', '')
                    }
        
        return None
        
    except Exception as e:
        print(f"Error getting lead from form responses: {e}")
        return None

def create_lead_in_odoo(url, session_id, lead_data):
    """Create lead in Odoo"""
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"session_id={session_id}"
    }

    # Check if lead already exists by email
    if lead_data['email']:
        search_data = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": "crm.lead",
                "method": "search_read",
                "args": [[["email_from", "=", lead_data['email']]]],
                "kwargs": {
                    "fields": ["id", "name"],
                    "limit": 1
                }
            }
        }

        response = requests.post(url + "/web/dataset/call_kw/crm.lead/search_read", 
                                 data=json.dumps(search_data), headers=headers)
        
        if response.status_code == 200:
            results = response.json().get("result", [])
            if results:
                print(f"Lead already exists: {results[0]['name']} (ID: {results[0]['id']})")
                return results[0]['id']

    # Create new lead
    lead_name = f"{lead_data['first_name']} {lead_data['last_name']}".strip()
    if lead_data['company']:
        lead_name += f" - {lead_data['company']}"

    odoo_lead_data = {
        "name": lead_name,
        "contact_name": f"{lead_data['first_name']} {lead_data['last_name']}".strip(),
        "email_from": lead_data['email'],
        "phone": lead_data['phone'],
        "partner_name": lead_data['company'],
        "type": "lead",
        "description": f"""Form Submission Details:
Industry: {lead_data.get('industry', 'Not specified')}
Whiteboard Type: {lead_data.get('whiteboard_type', 'Not specified')}  
Size: {lead_data.get('size', 'Not specified')}
Quantity: {lead_data.get('quantity', 'Not specified')}
Description: {lead_data.get('description', 'Not specified')}
Submission Date: {lead_data.get('submission_date', 'Not specified')}"""
    }

    create_data = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "crm.lead",
            "method": "create",
            "args": [odoo_lead_data],
            "kwargs": {}
        }
    }

    response = requests.post(url + "/web/dataset/call_kw/crm.lead/create", 
                             data=json.dumps(create_data), headers=headers)

    if response.status_code == 200 and response.json().get("result"):
        lead_id = response.json()["result"]
        print(f"✅ Created lead '{lead_name}' with ID: {lead_id}")
        return lead_id
    else:
        print(f"❌ Failed to create lead. Response: {response.json()}")
        return None

def main():
    print("🚀 Checking for new leads from processing queue...")
    
    # Authenticate with Google Sheets
    gc = authenticate_google_sheets()
    if not gc:
        return
    
    # Check processing queue
    pending_leads = check_processing_queue(gc)
    if not pending_leads:
        print("No new leads to process")
        return
    
    # Process only the LATEST pending lead (most recent)
    latest_lead = max(pending_leads, key=lambda x: x['timestamp'])
    print(f"Processing latest lead: {latest_lead['name']} (added: {latest_lead['timestamp']})")
    
    # Authenticate with Odoo
    session_id = authenticate_odoo(odoo_url, db, login, password)
    
    print(f"\n--- Processing: {latest_lead['name']} ---")
    
    # Get full lead data from form responses
    lead_data = get_lead_from_form_responses(gc, latest_lead['name'], latest_lead['email'])
    
    if not lead_data:
        print(f"❌ Could not find full data for {latest_lead['name']}")
        mark_lead_processed(gc, latest_lead['row'], 'ERROR')
        return
    
    # Create lead in Odoo
    lead_id = create_lead_in_odoo(odoo_url, session_id, lead_data)
    
    if lead_id:
        mark_lead_processed(gc, latest_lead['row'], 'PROCESSED')
        print(f"✅ Successfully processed latest lead: {latest_lead['name']}")
    else:
        mark_lead_processed(gc, latest_lead['row'], 'FAILED')
        print(f"❌ Failed to process latest lead: {latest_lead['name']}")

if __name__ == '__main__':
    main()
