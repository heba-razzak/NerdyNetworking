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

def gmail_authenticate():
    # If modifying these scopes, delete the file token.json.
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json", SCOPES
        )
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
        token.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    return service

def fetch_all_emails(service, user_id='me'):
    """
    Fetch all email message IDs from the user's inbox, handling pagination.
    Returns a list of message ID dictionaries.
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

