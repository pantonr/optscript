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
CSV_DATA_WORKSHEET_NAME = 'gpt_ss_data'
OTHER_FILES_WORKSHEET_NAME = 'gpt_other_files'

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

def get_csv_data(sheets_client):
    """Get CSV data from the gpt_ss_data tab"""
    try:
        spreadsheet = sheets_client.open_by_key(SPREADSHEET_ID)
        csv_worksheet = spreadsheet.worksheet(CSV_DATA_WORKSHEET_NAME)
        
        # Get all values from the CSV tab
        all_values = csv_worksheet.get_all_values()
        
        if all_values:
            print(f"✓ Found CSV data: {len(all_values)} rows")
            
            # Format as CSV-like text for GPT
            csv_text = "\n".join([",".join(row) for row in all_values])
            return csv_text
        else:
            print("✓ No CSV data found")
            return None
            
    except Exception as e:
        print(f"✗ Error getting CSV data: {e}")
        return None

def get_other_files(sheets_client):
    """Get support file links from the gpt_other_files tab"""
    try:
        spreadsheet = sheets_client.open_by_key(SPREADSHEET_ID)
        files_worksheet = spreadsheet.worksheet(OTHER_FILES_WORKSHEET_NAME)
        
        # Get all values starting from A2
        all_values = files_worksheet.get_all_values()
        
        file_links = []
        for i, row in enumerate(all_values):
            if i == 0:  # Skip header row
                continue
            if row and row[0]:  # If there's content in column A
                file_links.append(row[0])
        
        if file_links:
            print(f"✓ Found {len(file_links)} support file links")
            return file_links
        else:
            print("✓ No support files found")
            return []
            
    except Exception as e:
        print(f"✗ Error getting support files: {e}")
        return []

def get_instructions(sheets_client):
    """Get instructions from the instructions tab, cell A1"""
    try:
        spreadsheet = sheets_client.open_by_key(SPREADSHEET_ID)
        instructions_worksheet = spreadsheet.worksheet(INSTRUCTIONS_WORKSHEET_NAME)
        
        # Get the instruction from cell A1
        instruction = instructions_worksheet.acell('A1').value
        
        if instruction:
            print(f"✓ Found instructions: {len(instruction)} characters")
            return instruction
        else:
            print("✓ No instructions found in A1, using default")
            return None
            
    except Exception as e:
        print(f"✗ Error getting instructions: {e}")
        return None

def build_full_context(instructions, csv_data, file_links):
    """Build the complete context for GPT including all data and files"""
    context_parts = []
    
    # Add main instructions
    if instructions:
        context_parts.append("MAIN INSTRUCTIONS:")
        context_parts.append(instructions)
        context_parts.append("")
    
    # Add CSV data
    if csv_data:
        context_parts.append("CSV DATA (MyWhiteBoards.com URLs):")
        context_parts.append(csv_data)
        context_parts.append("")
    
    # Add support file links
    if file_links:
        context_parts.append("SUPPORT FILES:")
        for i, link in enumerate(file_links, 1):
            context_parts.append(f"File {i}: {link}")
        context_parts.append("")
    
    # Add the actual question
    context_parts.append("QUESTION: How are you?")
    
    return "\n".join(context_parts)

def ask_gpt_with_context(full_context):
    """Ask GPT with the complete context"""
    try:
        # Get API key from environment
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY environment variable")
        
        # Set up OpenAI client
        client = openai.OpenAI(api_key=api_key)
        
        print(f"✓ Sending {len(full_context)} characters to GPT")
        
        # Ask GPT with full context
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",  # Using GPT-4 for better handling of large contexts
            messages=[
                {"role": "user", "content": full_context}
            ],
            max_tokens=1000
        )
        
        gpt_response = response.choices[0].message.content.strip()
        print(f"✓ GPT responded: {gpt_response[:200]}...")
        return gpt_response
        
    except Exception as e:
        error_msg = f"Error asking GPT: {e}"
        print(f"✗ {error_msg}")
        return error_msg

def write_to_spreadsheet(sheets_client, gpt_response, context_summary):
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
            headers = ['Timestamp', 'Context Summary', 'GPT Response']
            worksheet.update(
                values=[headers],
                range_name='A1:C1'
            )
            next_row = 2
        
        # Write the data
        row_data = [timestamp, context_summary, gpt_response]
        worksheet.update(
            values=[row_data],
            range_name=f'A{next_row}:C{next_row}'
        )
        
        print(f"✓ Successfully wrote data to row {next_row}")
        return True
        
    except Exception as e:
        print(f"✗ Error writing to spreadsheet: {e}")
        traceback.print_exc()
        return False

def main():
    print("Starting GPT Health Check with Full Context...")
    print(f"Target spreadsheet: {SPREADSHEET_ID}")
    
    try:
        # Authenticate with Google Sheets
        sheets_client = authenticate_sheets()
        if not sheets_client:
            return False
        
        # Gather all context
        instructions = get_instructions(sheets_client)
        csv_data = get_csv_data(sheets_client)
        file_links = get_other_files(sheets_client)
        
        # Build full context for GPT
        full_context = build_full_context(instructions, csv_data, file_links)
        
        # Create summary for logging
        context_summary = f"Instructions: {'Yes' if instructions else 'No'}, CSV: {'Yes' if csv_data else 'No'}, Files: {len(file_links)}"
        
        # Ask GPT with complete context
        gpt_response = ask_gpt_with_context(full_context)
        
        # Write to spreadsheet
        success = write_to_spreadsheet(sheets_client, gpt_response, context_summary)
        
        if success:
            print("✓ GPT health check with full context completed successfully!")
        else:
            print("✗ GPT health check failed")
        
        return success
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()
