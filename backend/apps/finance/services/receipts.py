"""
Donation receipts as WhatsApp click-to-send links.

The admin opens the link, WhatsApp opens with the message ready, and they press
send. No paid WhatsApp API needed yet (that comes with the notifications module).
"""

import re
from urllib.parse import quote

from apps.finance.models import Donation


def receipt_message(donation: Donation) -> str:
    donor = donation.donor.public_name if donation.donor else "Donor"
    return (
        f"السلام علیکم {donor}،\n"
        f"جزاک اللہ! {donation.society.name} کو آپ کا عطیہ موصول ہو گیا۔\n\n"
        f"Assalam o Alaikum {donor},\n"
        f"JazakAllah! {donation.society.name} has received your donation.\n\n"
        f"Receipt: {donation.receipt_no}\n"
        f"Amount: Rs {donation.amount:,.0f}\n"
        f"Fund: {donation.fund.name}\n"
        f"Date: {donation.received_on:%d %b %Y}"
    )


def whatsapp_receipt_url(donation: Donation) -> str | None:
    if donation.status != Donation.Status.APPROVED or not donation.donor or not donation.donor.phone:
        return None
    digits = re.sub(r"\D", "", donation.donor.phone)
    if digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):  # local Pakistani number like 0300...
        digits = "92" + digits[1:]
    return f"https://wa.me/{digits}?text={quote(receipt_message(donation))}"
