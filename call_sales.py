import requests
import json
import re
import os
from datetime import datetime, timedelta, timezone

# Get credentials from environment variables (GitHub Secrets)
CALLRAIL_API_KEY = os.environ.get('CALLRAIL_API_KEY')
CALLRAIL_ACCOUNT_ID = os.environ.get('CALLRAIL_ACCOUNT_ID')

# Odoo credentials from environment variables
odoo_url = os.environ.get('ODOO_URL')
db = os.environ.get('ODOO_DB')
login = os.environ.get('ODOO_LOGIN')
password = os.environ.get('ODOO_PASSWORD')

# Validate that all required environment variables are present
required_env_vars = [
    'CALLRAIL_API_KEY', 'CALLRAIL_ACCOUNT_ID',
    'ODOO_URL', 'ODOO_DB', 'ODOO_LOGIN', 'ODOO_PASSWORD'
]

missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Map sources to IDs
source_mapping = {
    "Google Ads": 308,
    "Bing Ads": 371,
    "Facebook": 4,
    "LinkedIn": 6,
    "LinkedIn Ad": 6
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
    "Website": 1
}

# Function to authenticate to Odoo
def authenticate_odoo(url, db, login, password):
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
        return response.cookies.get('session_id')
    else:
        print(f"Failed to authenticate. Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        raise ValueError("Authentication failed")

# Function to normalize phone numbers to the last 10 digits
def normalize_phone(phone):
    cleaned_phone = re.sub(r'\D', '', phone)  # Remove all non-digit characters
    if len(cleaned_phone) > 10 and cleaned_phone.startswith('1'):
        cleaned_phone = cleaned_phone[1:]  # Remove leading '1' for US numbers
    return cleaned_phone[-10:]  # Return the last 10 digits

# Function to find leads or opportunities by phone number in Odoo
def find_crm_records_by_phone(url, session_id, phone):
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"session_id={session_id}"
    }

    data = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "crm.lead",
            "method": "search_read",
            "args": [[["phone", "!=", False]]],  # Get both leads and opportunities
            "kwargs": {
                "fields": ["id", "name", "phone"],
                "limit": 0
            }
        }
    }

    response = requests.post(url + "/web/dataset/call_kw/crm.lead/search_read", data=json.dumps(data), headers=headers)

    if response.status_code == 200:
        matching_records = []
        result = response.json().get("result", [])
        for record in result:
            record_phone_normalized = normalize_phone(record['phone'])
            if record_phone_normalized == phone:
                matching_records.append(record)
        return matching_records
    else:
        print(f"Failed to fetch CRM records. Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return []

# Function to find or create a campaign by name in Odoo
def get_or_create_campaign_id(url, session_id, campaign_name):
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
        print(f"Response: {response.json()}")
        return None

# Function to create a new campaign in Odoo
def create_campaign(url, session_id, campaign_name):
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
        print(f"Response: {response.json()}")
        return None

# Function to update CRM records and find related sales orders
def update_crm_records(url, session_id, phone_to_find, call_data):
    source_id = source_mapping.get(call_data.get('source'), None)
    campaign_name = call_data.get('campaign') if call_data.get('campaign') else "Test"
    campaign_id = get_or_create_campaign_id(url, session_id, campaign_name)
    
    medium = call_data.get('medium', '')
    medium_id = medium_mapping.get(medium)

    if medium_id is None:
        medium_lower = medium.lower()
        for key, value in medium_mapping.items():
            if key.lower() == medium_lower:
                medium_id = value
                break

    updated_data = {
        'source_id': source_id,
        'campaign_id': campaign_id,
        'medium_id': medium_id,
        'website': call_data.get('website'),
        'referred': 'CallRail'
    }

    crm_records = find_crm_records_by_phone(url, session_id, phone_to_find)
    
    if crm_records:
        print(f"Found {len(crm_records)} CRM records with the phone number {phone_to_find}.")
        for record in crm_records:
            print(f"Updating CRM Record ID {record['id']}, Name={record['name']}, Phone={record['phone']}")
            update_record(url, session_id, record['id'], updated_data, "crm.lead")
            
            print("\nChecking for related records...")
            find_related_records(url, session_id, record['id'], updated_data)
            print("------------------------")
    else:
        print(f"No CRM records found with the phone number {phone_to_find}.")

# Function to update a record in Odoo
def update_record(url, session_id, record_id, updated_data, model):
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"session_id={session_id}"
    }

    data = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": model,
            "method": "write",
            "args": [[record_id], updated_data],
            "kwargs": {}
        }
    }

    response = requests.post(url + "/web/dataset/call_kw/" + model + "/write", data=json.dumps(data), headers=headers)

    if response.status_code == 200 and response.json().get("result"):
        print(f"Record ID {record_id} in {model} successfully updated.")
    else:
        print(f"Failed to update record. Status Code: {response.status_code}")
        print(f"Response: {response.json()}")

# Function to find and update related sales orders
def find_related_records(url, session_id, lead_id, updated_data):
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"session_id={session_id}"
    }

    lead_data = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "crm.lead",
            "method": "read",
            "args": [lead_id],
            "kwargs": {"fields": ["partner_id", "phone"]}
        }
    }

    response = requests.post(
        url + "/web/dataset/call_kw/crm.lead/read",
        data=json.dumps(lead_data),
        headers=headers
    )

    if response.status_code == 200:
        lead_info = response.json().get("result", [{}])[0]
        partner_id = lead_info.get('partner_id', [False])[0] if lead_info.get('partner_id') else False

        if partner_id:
            sale_data = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "model": "sale.order",
                    "method": "search_read",
                    "args": [[("partner_id", "=", partner_id)]],
                    "kwargs": {
                        "fields": ["name"],
                        "limit": 0
                    }
                }
            }

            sale_response = requests.post(
                url + "/web/dataset/call_kw/sale.order/search_read",
                data=json.dumps(sale_data),
                headers=headers
            )

            if sale_response.status_code == 200:
                sales = sale_response.json().get("result", [])
                if sales:
                    print("\nRelated Sales Orders:")
                    for sale in sales:
                        print(f"- SO Number: {sale['name']}")
                        utm_data = {
                            'source_id': updated_data.get('source_id'),
                            'campaign_id': updated_data.get('campaign_id'),
                            'medium_id': updated_data.get('medium_id')
                        }
                        update_record(url, session_id, sale['id'], utm_data, "sale.order")

# Function to get the last 5 hours of calls from CallRail
def get_last_5_hours_calls():
    api_url = f"https://api.callrail.com/v3/a/{CALLRAIL_ACCOUNT_ID}/calls.json"
    
    now = datetime.now(timezone.utc)
    five_hours_ago = now - timedelta(hours=240)

    now_iso = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    five_hours_ago_iso = five_hours_ago.strftime('%Y-%m-%dT%H:%M:%SZ')

    headers = {
        'Authorization': f'Token token={CALLRAIL_API_KEY}',
        'Content-Type': 'application/json'
    }

    params = {
        'start_date': five_hours_ago_iso,
        'end_date': now_iso,
        'fields': 'source,campaign,landing_page_url,customer_phone_number,medium'
    }

    print(f"Fetching calls between {five_hours_ago_iso} and {now_iso}")
    
    response = requests.get(api_url, headers=headers, params=params)

    if response.status_code == 200:
        calls = response.json().get('calls', [])
        print(f"Retrieved {len(calls)} call(s) from the last 5 hours:")
        for call in calls:
            landing_page_url = call.get('landing_page_url')
            call['website'] = landing_page_url.split('?')[0] if landing_page_url else None
            print(json.dumps(call, indent=2))
        return calls
    else:
        print(f"Failed to retrieve calls. Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return []

# Main function
def main():
    session_id = authenticate_odoo(odoo_url, db, login, password)
    calls = get_last_5_hours_calls()
    for call in calls:
        phone_to_find = normalize_phone(call['customer_phone_number'])
        update_crm_records(odoo_url, session_id, phone_to_find, call)

if __name__ == '__main__':
    main()