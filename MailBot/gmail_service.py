import os
import base64
import re
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Якщо змінюємо права доступу, видаляємо token.json
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


class GmailService:
    def __init__(self):
        self.creds = None
        self.service = None
        self.authenticate()

    def authenticate(self):
        """
        Перевіряє наявність файлу token.json.
        """
        if os.path.exists('token.json'):
            self.creds = Credentials.from_authorized_user_file('token.json', SCOPES)

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"Помилка оновлення токена: {e}")
                    self.creds = None

            if not self.creds:
                if os.path.exists('credentials.json'):
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', SCOPES)
                    self.creds = flow.run_local_server(port=0)
                    with open('token.json', 'w') as token:
                        token.write(self.creds.to_json())
                else:
                    raise FileNotFoundError("Не знайдено credentials.json або token.json!")

        self.service = build('gmail', 'v1', credentials=self.creds)

    def send_message(self, recipient, subject, message_text):
        """Створює та відправляє email."""
        try:
            message = MIMEText(message_text)
            message['to'] = recipient
            message['subject'] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            body = {'raw': raw}

            sent_message = self.service.users().messages().send(userId="me", body=body).execute()
            return sent_message
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def get_latest_emails(self, count=5):
        """Отримує заголовки останніх N листів."""
        try:
            results = self.service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=count).execute()
            messages = results.get('messages', [])

            email_data = []
            for msg in messages:
                txt = self.service.users().messages().get(userId='me', id=msg['id']).execute()
                payload = txt['payload']
                headers = payload.get('headers', [])

                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "Без теми")
                sender = next((h['value'] for h in headers if h['name'] == 'From'), "Невідомий")
                snippet = txt.get('snippet', '')

                email_data.append({
                    'id': msg['id'],
                    'sender': sender,
                    'subject': subject,
                    'snippet': snippet
                })
            return email_data
        except Exception as e:
            print(f"Error getting emails: {e}")
            return []

    def get_full_message_text(self, msg_id):
        """Отримує повний текст листа за його ID з очисткою HTML."""
        try:
            msg = self.service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            payload = msg['payload']

            # Рекурсивна функція для пошуку тексту та його типу
            def find_text_part(parts):
                # 1. Спочатку шукаємо plain text (найкращий варіант)
                for part in parts:
                    if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                        return part['body']['data'], 'text/plain'

                # 2. Якщо не знайшли, заходимо всередину multipart (рекурсія)
                for part in parts:
                    if 'parts' in part:
                        data, mime = find_text_part(part['parts'])
                        if data:
                            return data, mime

                # 3. Якщо plain text немає, беремо HTML
                for part in parts:
                    if part['mimeType'] == 'text/html' and 'data' in part['body']:
                        return part['body']['data'], 'text/html'

                return None, None

            data, mime_type = None, None

            if 'parts' in payload:
                data, mime_type = find_text_part(payload['parts'])
            else:
                # Якщо лист простий (не multipart)
                data = payload['body'].get('data')
                mime_type = payload.get('mimeType')

            if data:
                text = base64.urlsafe_b64decode(data).decode('utf-8')

                # Якщо це HTML, чистимо теги
                if mime_type == 'text/html':
                    # Видаляємо вміст <head>, <style>, <script>
                    text = re.sub(r'<head.*?>.*?</head>', '', text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r'<style.*?>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)

                    # Замінюємо <br> та <p> на нові рядки
                    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
                    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)

                    # Видаляємо всі інші HTML теги
                    text = re.sub(r'<[^>]+>', '', text)

                    # Прибираємо зайві пробіли та порожні рядки
                    text = re.sub(r'\n\s*\n', '\n\n', text).strip()

                return text

            return "⚠️ Не вдалося розпізнати текст листа (можливо, це зображення)."

        except Exception as e:
            return f"Помилка при завантаженні листа: {e}"