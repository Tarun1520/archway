"""
Brevo as the email sender (brevo.com: free plan, 300 emails a day, no card).

One HTTPS request per email to Brevo's transactional email API. The key goes only in the `api-key` request header,
from here; it is never sent to the browser.

The sender address (MAIL_FROM) must be verified in Brevo first (Senders, domains & dedicated IPs → Senders), or Brevo
refuses the email.
"""

import httpx

from app.mail.base import MailError

SEND_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoMailer:
    def __init__(self, api_key: str, sender_email: str, sender_name: str):
        self._key = api_key
        self._sender = {"email": sender_email, "name": sender_name}

    async def send(self, *, to: str, subject: str, text: str, html: str) -> None:
        body = {"sender": self._sender, "to": [{"email": to}], "subject": subject, "textContent": text, "htmlContent": html}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(SEND_URL, json=body, headers={"api-key": self._key, "accept": "application/json"})
        except httpx.HTTPError as error:
            raise MailError(f"could not reach Brevo: {type(error).__name__}") from None
        if response.status_code >= 300:
            raise MailError(f"Brevo answered {response.status_code}: {response.text[:200]}")
