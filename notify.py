# notify.py — owner notifications
import os, smtplib
from email.message import EmailMessage
from typing import Optional
from twilio.rest import Client as Twilio

class Notifier:
    def __init__(self):
        self.email_from = os.getenv("II_EMAIL_FROM")
        self.email_to   = os.getenv("II_EMAIL_TO")
        self.smtp_host  = os.getenv("II_SMTP_HOST")
        self.smtp_user  = os.getenv("II_SMTP_USER")
        self.smtp_pass  = os.getenv("II_SMTP_PASS")
        self.tw_sid     = os.getenv("TWILIO_SID")
        self.tw_token   = os.getenv("TWILIO_TOKEN")
        self.tw_from    = os.getenv("TWILIO_FROM")
        self.tw_to      = os.getenv("TWILIO_TO")

        self.twilio: Optional[Twilio] = None
        if self.tw_sid and self.tw_token:
            try:
                self.twilio = Twilio(self.tw_sid, self.tw_token)
            except Exception:
                self.twilio = None

    def _email(self, subject: str, body: str):
        if not all([self.email_from, self.email_to, self.smtp_host]): return
        msg = EmailMessage()
        msg["From"] = self.email_from
        msg["To"]   = self.email_to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP_SSL(self.smtp_host, 465) as s:
            if self.smtp_user and self.smtp_pass:
                s.login(self.smtp_user, self.smtp_pass)
            s.send_message(msg)

    def _sms(self, body: str):
        if not self.twilio or not (self.tw_from and self.tw_to): return
        try:
            self.twilio.messages.create(from_=self.tw_from, to=self.tw_to, body=body)
        except Exception:
            pass

    def notify(self, subject: str, body: str):
        self._email(subject, body)
        self._sms(f"{subject} — {body}")
