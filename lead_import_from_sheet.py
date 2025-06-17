import requests
import json
import re
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import os

# Google Sheets Configuration
SERVICE_ACCOUNT_FILE = 'service_account.json'
SPREADSHEET_ID = '1GB1uBtCM58cER-Dnf3M6K7MLCZKpvTl7USLu6ns3hB0'  # Your new sheet
WORKSHEET_NAME = 'Form responses'

# Odoo TEST credentials - using QA environment
odoo_url = os.environ.get('ODOO_URL', 'https://qa-odoo.apps.optimacompanies.com/')
db = os.environ.get('ODOO_DB', 'prod-restore-20250409')
login = os.environ.get('ODOO_LOGIN')
password = os.environ.get('ODOO_PASSWORD')

# Map sources to IDs (these may need to be adjusted for the test environment)
source_mapping = {
    "Google Ads": 308,
    "Bing Ads": 371,
    "Facebook": 4,
    "LinkedIn": 6,
    "LinkedIn Ad": 6,
    "google": 308,
    "bing": 371,
    "facebook": 4,
    "linkedin": 6
}

# Map mediums to IDs
medium_mapping = {
    "2024 MWB Opti-Rite": 67,
    "Apollo": 61,
    "Banner": 5,
    "Chat": 62,
    "Cold Outreach": 60,
    "cpc": 66,
    "Direct": 3,
    "Email": 4,
    "Facebook": 7,
    "Form Fill": 63,
    "Google Adwords": 10,
    "LinkedIn": 8,
    "Paid": 65,
    "Phone": 2,
    "Printed Dry Erase": 41,
    "SMS": 12,
    "Twitter": 6,
    "Website": 1,
    "organic": 1,
    "social": 7,
    "referral": 1
}

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
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
        print(f"Response: {response.json()}")
        raise ValueError("Odoo authentication failed")

def normalize_phone(phone):
    """Normalize phone numbers to the last 10 digits"""
    if not phone:
        return ''
    cleaned_phone = re.sub(r'\D', '', phone)
    if len(cleaned_phone) > 10 and cleaned_phone.startswith('1'):
        cleaned_phone = cleaned_phone[1:]
    return cleaned_phone[-10:] if len(cleaned_phone) >= 10 else cleaned_phone

def get_or_create_campaign_id(url, session_id, campaign_name):
    """Find or create a campaign by name in Odoo"""
    if not campaign_name:
        campaign_name = "Website Form Submission"
    
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"session_id={session_id}"
    }
    
    campaign_name = campaign_name.strip()
    print(f"Searching for campaign with name: '{campaign_name}'")

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
                             data=json.dumps(search_data), 
                             headers=headers)
    
    if response.status_code == 200:
        result = response.json().get("result", [])
        if result:
            print(f"Found campaign in Odoo: '{result[0]['name']}' with ID {result[0]['id']}")
            return result[0]['id']
        else:
            print(f"No matching campaign found, creating a new one with name: '{campaign_name}'")
            return create_campaign(url, session_id, campaign_name)
    else:
        print(f"Failed to search campaign. Status Code: {response.status_code}")
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
                             data=json.dumps(create_data), 
                             headers=headers)
    
    if response.status_code == 200 and response.json().get("result"):
        new_campaign_id = response.json()["result"]
        print(f"Created new campaign '{campaign_name}' with ID {new_campaign_id}")
        return new_campaign_id
    else:
        print(f"Failed to create campaign. Status Code: {response.status_code}")
        return None

def check_existing_lead(url, session_id, email, phone):
    """Check if a lead already exists with this email or phone"""
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"session_id={session_id}"
    }

    # Search by email first
    if email:
        search_data = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": "crm.lead",
                "method": "search_read",
                "args": [[["email_from", "=", email]]],
                "kwargs": {
                    "fields": ["id", "name", "email_from", "phone"],
                    "limit": 1
                }
            }
        }

        response = requests.post(url + "/web/dataset/call_kw/crm.lead/search_read", 
                                 data=json.dumps(search_data), headers=headers)
        
        if response.status_code == 200:
            result = response.json().get("result", [])
            if result:
                return result[0]

    # If no email match, search by phone
    if phone:
        normalized_phone = normalize_phone(phone)
        search_data = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": "crm.lead",
                "method": "search_read",
                "args": [[["phone", "!=", False]]],
                "kwargs": {
                    "fields": ["id", "name", "email_from", "phone"],
                    "limit": 0
                }
            }
        }

        response = requests.post(url + "/web/dataset/call_kw/crm.lead/search_read", 
                                 data=json.dumps(search_data), headers=headers)
        
        if response.status_code == 200:
            results = response.json().get("result", [])
            for record in results:
                if normalize_phone(record.get('phone', '')) == normalized_phone:
                    return record
    
    return None

def create_lead_from_form(url, session_id, form_data):
    """Create a new lead in Odoo from form data"""
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"session_id={session_id}"
    }

    # Check if lead already exists
    existing_lead = check_existing_lead(url, session_id, 
                                       form_data.get('email'), 
                                       form_data.get('phone'))
    
    if existing_lead:
        print(f"Lead already exists: {existing_lead['name']} (ID: {existing_lead['id']})")
        print("Skipping creation...")
        return existing_lead['id']

    # Get campaign ID
    campaign_name = form_data.get('campaign_source', 'Website Form Submission')
    if not campaign_name:
        campaign_name = 'Website Form Submission'
    campaign_id = get_or_create_campaign_id(url, session_id, campaign_name)
    
    # Get source and medium IDs
    source_id = source_mapping.get(form_data.get('campaign_source', '').lower())
    medium_id = medium_mapping.get(form_data.get('campaign_medium', '').lower())

    # Create lead name
    first_name = form_data.get('first_name', '').strip()
    last_name = form_data.get('last_name', '').strip()
    company = form_data.get('company', '').strip()
    
    if first_name and last_name:
        lead_name = f"{first_name} {last_name}"
        if company:
            lead_name += f" - {company}"
    elif company:
        lead_name = company
    else:
        lead_name = "Website Form Submission"

    # Prepare lead creation data
    lead_data = {
        "name": lead_name,
        "contact_name": f"{first_name} {last_name}".strip(),
        "email_from": form_data.get('email'),
        "phone": form_data.get('phone'),
        "partner_name": company,
        "type": "lead",
        "description": f"""Form Submission Details:
Industry: {form_data.get('industry', 'Not specified')}
Whiteboard Type: {form_data.get('whiteboard_type', 'Not specified')}  
Size: {form_data.get('size', 'Not specified')}
Quantity: {form_data.get('quantity', 'Not specified')}
Description: {form_data.get('description', 'Not specified')}
Submission Date: {form_data.get('submission_date', 'Not specified')}
Submission ID: {form_data.get('submission_id', 'Not specified')}"""
    }

    # Add UTM data if available
    if campaign_id:
        lead_data['campaign_id'] = campaign_id
    if source_id:
        lead_data['source_id'] = source_id
    if medium_id:
        lead_data['medium_id'] = medium_id
    if form_data.get('campaign_landing_page'):
        lead_data['website'] = form_data['campaign_landing_page']

    create_data = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "crm.lead",
            "method": "create",
            "args": [lead_data],
            "kwargs": {}
        }
    }

    response = requests.post(url + "/web/dataset/call_kw/crm.lead/create", 
                             data=json.dumps(create_data), headers=headers)

    if response.status_code == 200 and response.json().get("result"):
        lead_id = response.json()["result"]
        print(f"Successfully created lead '{lead_name}' with ID: {lead_id}")
        return lead_id
    else:
        print(f"Failed to create lead. Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return None

def read_form_responses(gc):
    """Read form responses from Google Sheet"""
    try:
        sheet = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sheet.worksheet(WORKSHEET_NAME)
        
        all_values = worksheet.get_all_values()
        headers = all_values[0]
        
        form_responses = []
        for row in all_values[1:]:
            if len(row) >= len(headers):
                form_data = {}
                for i, header in enumerate(headers):
                    form_data[header] = row[i] if i < len(row) else ''
                
                # Map to our expected field names
                mapped_data = {
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
                    'campaign_source': form_data.get('campaign_source', ''),
                    'campaign_medium': form_data.get('campaign_medium', ''),
                    'campaign_referrer_url': form_data.get('campaign_referrer_url', ''),
                    'campaign_landing_page': form_data.get('campaign_landing_page', ''),
                    'campaign_session_timestamp': form_data.get('campaign_session_timestamp', ''),
                    'submission_id': form_data.get('Submission ID', '')
                }
                
                # Only add if we have at least a name or email
                if mapped_data['first_name'] or mapped_data['email']:
                    form_responses.append(mapped_data)
        
        print(f"Found {len(form_responses)} form responses to process")
        return form_responses
        
    except Exception as e:
        print(f"Error reading Google Sheet: {e}")
        return []

def main():
    print("🧪 Using Odoo TEST Environment")
    print(f"URL: {odoo_url}")
    print(f"Database: {db}")
    print()
    
    print("Authenticating with Google Sheets...")
    gc = authenticate_google_sheets()
    if not gc:
        print("Failed to authenticate with Google Sheets. Exiting.")
        return
    
    print("Authenticating with Odoo TEST environment...")
    session_id = authenticate_odoo(odoo_url, db, login, password)

    print("Reading form responses...")
    form_responses = read_form_responses(gc)

    if not form_responses:
        print("No form responses found. Exiting.")
        return

    successful_leads = 0
    for i, form_data in enumerate(form_responses, 1):
        print(f"\n--- Processing form response {i}/{len(form_responses)} ---")
        print(f"Name: {form_data['first_name']} {form_data['last_name']}")
        print(f"Email: {form_data['email']}")
        print(f"Company: {form_data['company']}")
        
        lead_id = create_lead_from_form(odoo_url, session_id, form_data)
        if lead_id:
            successful_leads += 1
    
    print(f"\n--- SUMMARY ---")
    print(f"Total form responses: {len(form_responses)}")
    print(f"Successfully created leads: {successful_leads}")
    print(f"Skipped/Failed: {len(form_responses) - successful_leads}")

if __name__ == '__main__':
    main()
