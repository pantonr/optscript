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
odoo_url = os.environ.get('ODOO_URL', 'https://odoo.optimacompanies.com/')
db = os.environ.get('ODOO_DB', 'master')
login = os.environ.get('ODOO_LOGIN')
password = os.environ.get('ODOO_PASSWORD')

# Salesperson assignment
MIKE_GOODWIN_USER_ID = 28

# Map sources to IDs (adjust these for your QA environment)
source_mapping = {
    "google": 308,
    "google ads": 308,
    "facebook": 4,
    "linkedin": 6,
    "bing": 371,
    "bing ads": 371,
    "twitter": 6,
    "instagram": 4,
    "youtube": 4
}

# Map mediums to IDs (adjust these for your QA environment)
medium_mapping = {
    "google ads": 10,
    "paid_social": 7,
    "cpc": 66,
    "organic": 1,
    "email": 4,
    "social": 7,
    "referral": 1,
    "direct": 3,
    "display": 5,
    "banner": 5,
    "phone": 2,
    "website": 1
}

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

def get_or_create_campaign_id(url, session_id, campaign_name):
    """Find or create a campaign by name in Odoo"""
    if not campaign_name:
        campaign_name = "Website Form Submission"
    
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"session_id={session_id}"
    }
    
    campaign_name = campaign_name.strip()
    print(f"🔍 Searching for campaign: '{campaign_name}'")

    # Search for existing campaign
    search_data = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "utm.campaign",
            "method": "search_read",
            "args": [[["name", "=", campaign_name]]],
            "kwargs": {
                "fields": ["id", "name"],
                "limit": 1
            }
        }
    }

    response = requests.post(url + "/web/dataset/call_kw/utm.campaign/search_read", 
                             data=json.dumps(search_data), headers=headers)
    
    if response.status_code == 200:
        result = response.json().get("result", [])
        if result:
            print(f"✅ Found existing campaign: '{result[0]['name']}' (ID: {result[0]['id']})")
            return result[0]['id']
        else:
            print(f"📝 Creating new campaign: '{campaign_name}'")
            return create_campaign(url, session_id, campaign_name)
    else:
        print(f"❌ Failed to search campaign. Status Code: {response.status_code}")
        return None

def create_campaign(url, session_id, campaign_name):
    """Create a new campaign in Odoo"""
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"session_id={session_id}"
    }

    create_data = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "utm.campaign",
            "method": "create",
            "args": [{
                "name": campaign_name
            }],
            "kwargs": {}
        }
    }

    response = requests.post(url + "/web/dataset/call_kw/utm.campaign/create", 
                             data=json.dumps(create_data), headers=headers)
    
    if response.status_code == 200 and response.json().get("result"):
        new_campaign_id = response.json()["result"]
        print(f"✅ Created new campaign '{campaign_name}' (ID: {new_campaign_id})")
        return new_campaign_id
    else:
        print(f"❌ Failed to create campaign. Status Code: {response.status_code}")
        return None

def check_processing_queue(gc):
    """Check for pending leads in processing queue"""
    try:
        sheet = gc.open_by_key(SPREADSHEET_ID)
        
        try:
            processing_sheet = sheet.worksheet(PROCESSING_QUEUE_NAME)
        except:
            print("No processing queue found")
            return []
        
        all_values = processing_sheet.get_all_values()
        if len(all_values) <= 1:
            print("No pending leads in processing queue")
            return []
        
        headers = all_values[0]
        pending_leads = []
        
        for i, row in enumerate(all_values[1:], start=2):
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
        processing_sheet.update_cell(row_number, 4, status)
        processing_sheet.update_cell(row_number, 1, datetime.now().isoformat())
    except Exception as e:
        print(f"Error marking lead as processed: {e}")

def get_lead_from_form_responses(gc, lead_name, lead_email):
    """Find full lead data from form responses - get the LATEST matching row"""
    try:
        sheet = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sheet.worksheet(WORKSHEET_NAME)
        
        all_values = worksheet.get_all_values()
        headers = all_values[0]
        
        matching_lead = None
        
        # Search from bottom up to get latest
        for row in reversed(all_values[1:]):
            if len(row) >= len(headers):
                row_first_name = row[1] if len(row) > 1 else ''
                row_last_name = row[2] if len(row) > 2 else ''
                row_email = row[4] if len(row) > 4 else ''
                
                full_name = f"{row_first_name} {row_last_name}".strip()
                
                print(f"Checking row: {full_name} ({row_email}) vs looking for: {lead_name} ({lead_email})")
                
                if (full_name == lead_name or row_email == lead_email) and row_email:
                    print(f"✅ Found matching lead: {full_name} with email {row_email}")
                    
                    # Map ALL the form data including UTM fields
                    form_data = {}
                    for i, header in enumerate(headers):
                        form_data[header] = row[i] if i < len(row) else ''
                    
                    matching_lead = {
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
                        'submission_id': form_data.get('Submission ID', ''),
                        # UTM Campaign Data
                        'campaign_source': form_data.get('campaign_source', ''),
                        'campaign_medium': form_data.get('campaign_medium', ''),
                        'campaign_campaign': form_data.get('campaign_campaign', ''),
                        'campaign_term': form_data.get('campaign_term', ''),
                        'campaign_content': form_data.get('campaign_content', ''),
                        'campaign_landing_page': form_data.get('campaign_landing_page', ''),
                        'campaign_referrer_url': form_data.get('campaign_referrer_url', ''),
                        'campaign_gclid': form_data.get('campaign_gclid', ''),
                        'campaign_matchtype': form_data.get('campaign_matchtype', ''),
                        'campaign_network': form_data.get('campaign_network', ''),
                        'campaign_device': form_data.get('campaign_device', ''),
                        'campaign_session_timestamp': form_data.get('campaign_session_timestamp', '')
                    }
                    break
        
        if matching_lead:
            print(f"Returning lead data for: {matching_lead['first_name']} {matching_lead['last_name']}")
            print(f"UTM Source: {matching_lead['campaign_source']}")
            print(f"UTM Medium: {matching_lead['campaign_medium']}")
            print(f"UTM Campaign: {matching_lead['campaign_campaign']}")
        else:
            print(f"No matching lead found for: {lead_name} ({lead_email})")
            
        return matching_lead
        
    except Exception as e:
        print(f"Error getting lead from form responses: {e}")
        return None

def create_lead_in_odoo(url, session_id, lead_data):
    """Create lead in Odoo with campaign/source/medium data"""
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

    # Get campaign ID from campaign name
    campaign_name = lead_data.get('campaign_campaign', 'Website Form Submission')
    if not campaign_name:
        campaign_name = 'Website Form Submission'
    campaign_id = get_or_create_campaign_id(url, session_id, campaign_name)
    
    # Get source and medium IDs
    source_name = lead_data.get('campaign_source', '').lower().strip()
    medium_name = lead_data.get('campaign_medium', '').lower().strip()
    
    source_id = source_mapping.get(source_name)
    medium_id = medium_mapping.get(medium_name)
    
    print(f"🏷️  UTM Mapping:")
    print(f"   Source: '{source_name}' → ID: {source_id}")
    print(f"   Medium: '{medium_name}' → ID: {medium_id}")
    print(f"   Campaign: '{campaign_name}' → ID: {campaign_id}")

    # Create new lead
    lead_name = f"{lead_data['first_name']} {lead_data['last_name']}".strip()
    if lead_data['company']:
        lead_name += f" - {lead_data['company']}"

    # Enhanced description with UTM data
    description = f"""Form Submission Details:
Industry: {lead_data.get('industry', 'Not specified')}
Whiteboard Type: {lead_data.get('whiteboard_type', 'Not specified')}  
Size: {lead_data.get('size', 'Not specified')}
Quantity: {lead_data.get('quantity', 'Not specified')}
Description: {lead_data.get('description', 'Not specified')}
Submission Date: {lead_data.get('submission_date', 'Not specified')}
Submission ID: {lead_data.get('submission_id', 'Not specified')}

Campaign Data:
Source: {lead_data.get('campaign_source', 'Not specified')}
Medium: {lead_data.get('campaign_medium', 'Not specified')}
Campaign: {lead_data.get('campaign_campaign', 'Not specified')}
Term: {lead_data.get('campaign_term', 'Not specified')}
Content: {lead_data.get('campaign_content', 'Not specified')}
Landing Page: {lead_data.get('campaign_landing_page', 'Not specified')}
GCLID: {lead_data.get('campaign_gclid', 'Not specified')}
Match Type: {lead_data.get('campaign_matchtype', 'Not specified')}
Network: {lead_data.get('campaign_network', 'Not specified')}
Device: {lead_data.get('campaign_device', 'Not specified')}"""

    odoo_lead_data = {
        "name": lead_name,
        "contact_name": f"{lead_data['first_name']} {lead_data['last_name']}".strip(),
        "email_from": lead_data['email'],
        "phone": lead_data['phone'],
        "partner_name": lead_data['company'],
        "type": "lead",
        "description": description,
        "referred": "Website Form",
        "user_id": MIKE_GOODWIN_USER_ID
    }

    # Add UTM data if available
    if campaign_id:
        odoo_lead_data['campaign_id'] = campaign_id
    if source_id:
        odoo_lead_data['source_id'] = source_id
    if medium_id:
        odoo_lead_data['medium_id'] = medium_id
    if lead_data.get('campaign_landing_page'):
        odoo_lead_data['website'] = lead_data['campaign_landing_page']

    print(f"📝 Creating lead with UTM data and Mike Goodwin (ID: {MIKE_GOODWIN_USER_ID}):")
    print(f"   Campaign ID: {campaign_id}")
    print(f"   Source ID: {source_id}")
    print(f"   Medium ID: {medium_id}")
    print(f"   Website: {lead_data.get('campaign_landing_page', 'Not set')}")

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
        print(f"✅ Created lead '{lead_name}' with ID: {lead_id} assigned to Mike Goodwin")
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
    
    # Process only the LAST pending lead in the queue
    latest_lead = max(pending_leads, key=lambda x: x['row'])
    print(f"Processing latest lead: {latest_lead['name']} (row: {latest_lead['row']})")
    
    # Authenticate with Odoo
    session_id = authenticate_odoo(odoo_url, db, login, password)
    
    print(f"\n--- Processing: {latest_lead['name']} ---")
    
    # Get full lead data from form responses
    lead_data = get_lead_from_form_responses(gc, latest_lead['name'], latest_lead['email'])
    
    if not lead_data:
        print(f"❌ Could not find full data for {latest_lead['name']}")
        mark_lead_processed(gc, latest_lead['row'], 'ERROR')
        return
    
    # Create lead in Odoo with campaign data
    lead_id = create_lead_in_odoo(odoo_url, session_id, lead_data)
    
    if lead_id:
        mark_lead_processed(gc, latest_lead['row'], 'PROCESSED')
        print(f"✅ Successfully processed latest lead: {latest_lead['name']} with campaign data")
    else:
        mark_lead_processed(gc, latest_lead['row'], 'FAILED')
        print(f"❌ Failed to process latest lead: {latest_lead['name']}")

if __name__ == '__main__':
    main()
