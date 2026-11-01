"""Builds the email sender from the settings, or None when it is not set up (password reset by email is then off)."""

from app.config.settings import Settings
from app.mail.base import Mailer
from app.mail.brevo import BrevoMailer


def build_mailer(settings: Settings) -> Mailer | None:
    if settings.brevo_api_key is None or not settings.mail_from:
        return None
    return BrevoMailer(settings.brevo_api_key.get_secret_value(), settings.mail_from, settings.mail_from_name)
