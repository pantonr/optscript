import os
import openai
import gspread
from google.oauth2.service_account import Credentials
import traceback
from datetime import datetime

# Configuration
SERVICE_ACCOUNT_FILE = 'service_account.json'
SPREADSHEET_ID = '1A5pOeD7VgAnZAoZWtNWe79LasLlEtkH85xY34RV01S4'
DATA_WORKSHEET_NAME = 'data'
INSTRUCTIONS_WORKSHEET_NAME = 'instructions'

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

def get_instructions(sheets_client):
    """Get instructions from the instructions tab, cell A1"""
    try:
        spreadsheet = sheets_client.open_by_key(SPREADSHEET_ID)
        instructions_worksheet = spreadsheet.worksheet(INSTRUCTIONS_WORKSHEET_NAME)
        
        # Get the instruction from cell A1
        instruction = instructions_worksheet.acell('A1').value
        
        if instruction:
            print(f"✓ Found instructions: '{instruction}'")
            return instruction
        else:
            print("✓ No instructions found in A1, using default")
            return None
            
    except Exception as e:
        print(f"✗ Error getting instructions: {e}")
        print("Using default question without instructions")
        return None

def ask_gpt_how_are_you(instructions=None):
    """Ask GPT 'how are you' with optional instructions"""
    try:
        # Get API key from environment
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY environment variable")
        
        # Set up OpenAI client
        client = openai.OpenAI(api_key=api_key)
        
        # Build the question with instructions if provided
        if instructions:
            question = f"{instructions}. How are you?"
            print(f"✓ Asking GPT with instructions: '{question}'")
        else:
            question = "How are you?"
            print(f"✓ Asking GPT: '{question}'")
        
        # Ask GPT the question
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": question}
            ],
            max_tokens=150
        )
        
        gpt_response = response.choices[0].message.content.strip()
        print(f"✓ GPT responded: {gpt_response}")
        return gpt_response, question
        
    except Exception as e:
        error_msg = f"Error asking GPT: {e}"
        print(f"✗ {error_msg}")
        return error_msg, "Error"

def write_to_spreadsheet(sheets_client, gpt_response, question, instructions):
    """Write the GPT response to the data worksheet"""
    try:
        # Open the spreadsheet and get the data worksheet
        spreadsheet = sheets_client.open_by_key(SPREADSHEET_ID)
        
        # Try to get the data worksheet, create if it doesn't exist
        try:
            worksheet = spreadsheet.worksheet(DATA_WORKSHEET_NAME)
            print(f"✓ Writing to existing worksheet: {worksheet.title}")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=DATA_WORKSHEET_NAME, rows=100, cols=10)
            print(f"✓ Created new worksheet: {worksheet.title}")
        
        # Get current timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Find the next empty row
        values = worksheet.col_values(1) if worksheet.col_values(1) else []
        next_row = len(values) + 1
        
        # Write headers if this is the first entry
        if next_row == 1:
            headers = ['Timestamp', 'Instructions Used', 'Question Asked', 'GPT Response']
            worksheet.update(
                values=[headers],
                range_name='A1:D1'
            )
            next_row = 2
        
        # Write the data
        row_data = [timestamp, instructions or "None", question, gpt_response]
        worksheet.update(
            values=[row_data],
            range_name=f'A{next_row}:D{next_row}'
        )
        
        print(f"✓ Successfully wrote data to row {next_row}")
        print(f"  Timestamp: {timestamp}")
        print(f"  Instructions: {instructions or 'None'}")
        print(f"  Question: {question}")
        print(f"  GPT Response: {gpt_response[:100]}...")  # Truncate for logs
        
        return True
        
    except Exception as e:
        print(f"✗ Error writing to spreadsheet: {e}")
        traceback.print_exc()
        return False

def main():
    print("Starting GPT Health Check...")
    print(f"Target spreadsheet: {SPREADSHEET_ID}")
    print(f"Data will be written to: '{DATA_WORKSHEET_NAME}' tab")
    print(f"Instructions will be read from: '{INSTRUCTIONS_WORKSHEET_NAME}' tab, cell A1")
    
    try:
        # Authenticate with Google Sheets
        sheets_client = authenticate_sheets()
        if not sheets_client:
            return False
        
        # Get instructions from the instructions tab
        instructions = get_instructions(sheets_client)
        
        # Ask GPT how it's doing (with instructions if available)
        gpt_response, question = ask_gpt_how_are_you(instructions)
        
        # Write to spreadsheet
        success = write_to_spreadsheet(sheets_client, gpt_response, question, instructions)
        
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
