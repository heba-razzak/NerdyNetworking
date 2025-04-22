import base64, email
from email.utils import parseaddr
from dotenv import load_dotenv
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
import re
import pandas as pd

def gmail_authenticate():
    # Define the Gmail API scope (read-only access)
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
    creds = None

    try:
        # Step 1: Load token if it exists
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)

        # Step 2: If no valid creds, refresh or log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Check for credentials file
                if not os.path.exists("credentials.json"):
                    raise FileNotFoundError("Missing credentials.json — download it from https://console.cloud.google.com/apis/credentials")
                
                # Browser login
                print("🔓 Opening browser for Google login...")
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)

            # Step 3: Confirm creds were received
            if not creds:
                raise RuntimeError("Authentication failed. No credentials received.")

            # Step 4: Save token for next time
            with open("token.json", "w") as token:
                token.write(creds.to_json())

        # Step 5: Build Gmail API service
        service = build("gmail", "v1", credentials=creds)
        return service
    
    except FileNotFoundError as e:
        print(f"❌ {e}")
    except RuntimeError as e:
        print(f"❌ {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def fetch_all_emails(service, user_id='me'):
    """
    Fetch all email message IDs from the user's inbox, handling pagination.
    Returns a list of message ID and thread ID dictionaries.
    """
    all_messages = []
    try:
        # Initial request for the first page of inbox messages (max 500 results)
        response = service.users().messages().list(userId=user_id, labelIds=['INBOX'], maxResults=500).execute()
        messages = response.get('messages', [])
        if messages:
            all_messages.extend(messages)
        # Continue fetching while a next page token exists
        while 'nextPageToken' in response:
            page_token = response['nextPageToken']
            response = service.users().messages().list(
                userId=user_id, labelIds=['INBOX'], maxResults=500, pageToken=page_token
            ).execute()
            messages = response.get('messages', [])
            if messages:
                all_messages.extend(messages)
        return all_messages
    except Exception as e:
        print(f"An error occurred while fetching emails: {e}")
        return []

def clean_spacing(text):
    """
    Thoroughly clean text by removing extra whitespace, newlines, tabs, and other
    unnecessary characters.
    
    Parameters:
        text (str): Raw text to clean
        
    Returns:
        str: Cleaned text
    """
    if not text:
        return ""
        
    # Replace tabs, carriage returns with spaces
    text = re.sub(r'[\t\r]', ' ', text)
    
    # Replace multiple newlines with a single newline
    text = re.sub(r'\n+', '\n', text)
    
    # Replace multiple spaces with a single space
    text = re.sub(r' +', ' ', text)
    
    # Remove newlines followed by spaces or vice versa
    text = re.sub(r'\n\s+', '\n', text)
    text = re.sub(r'\s+\n', '\n', text)
    
    # Final pass to catch any remaining sequences
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def parse_email(service, message_id, user_id='me'):
    """
    Retrieve an email by ID and extract required fields.
    Returns a dictionary with sender name, sender email, timestamp, subject, 
    plain text body, HTML body, company name (if found), job position (if found),
    and recruiter/hiring manager name (if found).
    """
    # Fetch the raw message payload from Gmail
    message = service.users().messages().get(userId=user_id, id=message_id, format='raw').execute()
    raw_data = message['raw']  # Base64url encoded string
    # Decode the base64url data to bytes, and parse into an EmailMessage
    msg_bytes = base64.urlsafe_b64decode(raw_data.encode('utf-8'))
    mime_msg = email.message_from_bytes(msg_bytes)  # Parse bytes to email message
    
    # Extract headers
    sender_name, sender_email = parseaddr(mime_msg.get('From', ''))
    timestamp = mime_msg.get('Date', '')
    subject = mime_msg.get('Subject', '')
    
    # Initialize body variables
    text_body = "" 
    html_body = ""
    # If the email is multipart, iterate through parts to get text/HTML content
    if mime_msg.is_multipart():
        for part in mime_msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get_content_disposition() or "")
            if ctype == 'text/plain' and 'attachment' not in disp:
                # Decode text/plain part
                text_bytes = part.get_payload(decode=True)
                if text_bytes:
                    text_body += text_bytes.decode('utf-8', errors='ignore')
            elif ctype == 'text/html' and 'attachment' not in disp:
                # Decode text/html part
                html_bytes = part.get_payload(decode=True)
                if html_bytes:
                    html_body = html_bytes.decode('utf-8', errors='ignore')
                    soup = BeautifulSoup(html_body, "html.parser")
                    text = clean_spacing(soup.get_text())
                    
                    # .replace('\xa0', '').strip()
                    # clean_text = re.sub(' +', ' ', text)
                    html_body += text
    else:
        # Not multipart (e.g., plain text only)
        body_bytes = mime_msg.get_payload(decode=True)
        if body_bytes:
            text_body = body_bytes.decode('utf-8', errors='ignore')

    # Return all extracted information
    return {
        "sender_name": sender_name or "",
        "sender_email": sender_email or "",
        "timestamp": timestamp,
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body
    }


def clean_html(html_content):
    """
    Removes HTML tags and returns only the plain text content.
    
    Parameters:
        html_content (str): HTML content as a string.
    
    Returns:
        str: Cleaned plain text content.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    text = ' '.join(soup.get_text(separator=' ').split())
    return text.replace('\n', ' ').strip()


def extract_plain_text(email_json):
    """
    Extracts and returns only the plain text from a Gmail API email JSON response.
    
    Parameters:
        email_json (dict): JSON response from the Gmail API.
        
    Returns:
        str: Cleaned plain text content of the email.
    """
    payload = email_json.get("payload", {})

    # Check if 'parts' exist (multipart email)
    if "parts" in payload:
        for part in payload["parts"]:
            mime_type = part.get("mimeType", "")
            body_data = part.get("body", {}).get("data", "")

            if body_data:
                decoded_data = base64.urlsafe_b64decode(body_data).decode("utf-8")

                if mime_type == "text/plain":
                    return decoded_data.strip()  # Clean plain text
                elif mime_type == "text/html":
                    return clean_html(decoded_data)  # Convert HTML to plain text

    # If no 'parts', check if 'body' contains the message
    body_data = payload.get("body", {}).get("data", "")
    if body_data:
        decoded_data = base64.urlsafe_b64decode(body_data).decode("utf-8")
        return clean_html(decoded_data)  # Convert HTML to plain text if necessary

    return ""  # Return empty string if no content is found

def email_ids_to_df(service, email_ids):
    """
    Converts a list of email IDs to a DataFrame.
    
    Parameters:
        email_ids (list): List of email IDs.
        
    Returns:
        pd.DataFrame: DataFrame containing email IDs and their corresponding data.
    """
    # Create empty lists to store data
    ids = []
    subjects = []
    senders = []
    sender_names = []
    sender_emails = []
    snippets = []
    bodies = []
    dates = []

    # get message data using id
    for email in email_ids:
        email_id = email["id"]
        msg_data = service.users().messages().get(userId="me", id=email_id).execute()
        email_content = extract_plain_text(msg_data)
        # Extract headers
        headers = msg_data["payload"]["headers"]
        # Get info from headers
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")
        date = next((h["value"] for h in headers if h["name"] == "Date"), "No Date")
        
        # Extract sender name and email if in <> format
        if '<' in sender and '>' in sender:
            sender_name = sender.split('<')[0].strip()
            sender_email = sender[sender.find('<')+1:sender.find('>')]
        else:
            sender_name = ""
            sender_email = sender

        if sender_name.startswith('"') and sender_name.endswith('"'):
            sender_name = sender_name[1:-1]

        # Append data to lists
        ids.append(email_id)
        subjects.append(subject)
        senders.append(sender)
        sender_names.append(sender_name)
        sender_emails.append(sender_email)
        snippets.append(msg_data.get('snippet', ''))
        bodies.append(email_content)
        # dates.append(msg_data.get('internalDate', ''))
        dates.append(date)

    # Create DataFrame from lists
    emails_df = pd.DataFrame({
        "Sender Name": sender_names,
        "Sender Email": sender_emails,
        'Subject': subjects, 
        'Body': bodies,
        # 'Date': dates,
        # 'ID': ids,
        # 'Sender': senders,
        # 'Snippet': snippets
        })
    return emails_df
