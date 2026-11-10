"""
Sending SMS. The real provider isn't chosen yet, so the sender is a setting:

    SMS_BACKEND = "apps.accounts.sms.ConsoleSMS"    development: prints the message to the log
    SMS_BACKEND = "apps.accounts.sms.DisabledSMS"   production default until a provider is set up

A provider (e.g. a Pakistani SMS gateway) is added later as another class with a send() method.
"""

import logging

from django.conf import settings
from django.utils.module_loading import import_string

log = logging.getLogger(__name__)


class ConsoleSMS:
    def send(self, phone: str, text: str) -> None:
        log.warning("SMS to %s: %s", phone, text)  # development only: shows the code in the log


class DisabledSMS:
    def send(self, phone: str, text: str) -> None:
        log.error("SMS to %s not sent: no SMS provider is configured (SMS_BACKEND).", phone)


def send_sms(phone: str, text: str) -> None:
    import_string(settings.SMS_BACKEND)().send(phone, text)


class MemorySMS:
    """For tests: keeps sent messages in a list instead of sending them."""

    outbox: list[tuple[str, str]] = []

    def send(self, phone: str, text: str) -> None:
        MemorySMS.outbox.append((phone, text))
