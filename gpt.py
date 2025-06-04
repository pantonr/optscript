import os
import openai
import gspread
from google.oauth2.service_account import Credentials
import traceback
from datetime import datetime

# Configuration
SERVICE_ACCOUNT_FILE = 'service_account.json'
SPREADSHEET_ID = '1A5pOeD7VgAnZAoZWtNWe79LasLlEtkH85xY34RV01S4'
WORKSHEET_NAME = 'Sheet1'  # Change if needed

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def authenticate_sheets():
    """Authenticate with Google Sheets"""
    try:
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        gc = gspread.authorize(credentials)
        print("✓ Successfully authenticated with Google Sheets")
        return gc
    except Exception as e:
        print(f"✗ Error authenticating with Google Sheets: {e}")
        return None

def ask_gpt_how_are_you():
    """Ask GPT 'how are you' and return the response"""
    try:
        # Get API key from environment
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY environment variable")
        
        # Set up OpenAI client
        client = openai.OpenAI(api_key=api_key)
        
        # Ask GPT the question
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "How are you?"}
            ],
            max_tokens=150
        )
        
        gpt_response = response.choices[0].message.content.strip()
        print(f"✓ GPT responded: {gpt_response}")
        return gpt_response
        
    except Exception as e:
        error_msg = f"Error asking GPT: {e}"
        print(f"✗ {error_msg}")
        return error_msg

def write_to_spreadsheet(sheets_client, gpt_response):
    """Write the GPT response to the spreadsheet"""
    try:
        # Open the spreadsheet
        spreadsheet = sheets_client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        
        # Get current timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Find the next empty row
        values = worksheet.col_values(1)
        next_row = len(values) + 1
        
        # Write headers if this is the first entry
        if next_row == 1:
            worksheet.update(
                values=[['Timestamp', 'Question', 'GPT Response']],
                range_name='A1:C1'
            )
            next_row = 2
        
        # Write the data
        worksheet.update(
            values=[[timestamp, 'How are you?', gpt_response]],
            range_name=f'A{next_row}:C{next_row}'
        )
        
        print(f"✓ Successfully wrote data to row {next_row}")
        print(f"  Timestamp: {timestamp}")
        print(f"  Question: How are you?")
        print(f"  GPT Response: {gpt_response}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error writing to spreadsheet: {e}")
        traceback.print_exc()
        return False

def main():
    print("Starting GPT Health Check...")
    print(f"Target spreadsheet: {SPREADSHEET_ID}")
    
    try:
        # Authenticate with Google Sheets
        sheets_client = authenticate_sheets()
        if not sheets_client:
            return False
        
        # Ask GPT how it's doing
        gpt_response = ask_gpt_how_are_you()
        
        # Write to spreadsheet
        success = write_to_spreadsheet(sheets_client, gpt_response)
        
        if success:
            print("✓ GPT health check completed successfully!")
        else:
            print("✗ GPT health check failed")
        
        return success
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()
