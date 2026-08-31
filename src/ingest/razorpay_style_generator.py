"""Generates synthetic Payments + Settlements data shaped exactly like
Razorpay's real API entities.

This project does not call the live Razorpay API — a real dashboard account
needs PAN-based KYC, which isn't available here. Instead, this module
produces data with the same field names and structure as Razorpay's actual
Payments and Settlements API responses (see razorpay.com/docs/api/payments/
and /settlements/), generated locally. The buildathon brief explicitly
allows a "50+ record batch of synthetic data," so this is within spec —
it's described honestly as synthetic throughout the project, styled after
the real schema rather than fetched live.

Field names intentionally match the real API so the rest of the pipeline
(matching engine, dashboard) would need no changes if real API data were
ever substituted in.
"""

import random
import string
from datetime import datetime, timedelta, timezone

from faker import Faker

METHODS = ["card", "upi", "netbanking", "wallet"]
# Weighted so most payments succeed, some fail/refund, like a real gateway.
STATUSES = ["captured", "captured", "captured", "captured", "failed", "refunded"]
BANKS = ["HDFC", "ICICI", "SBI", "AXIS", "KOTAK"]
WALLETS = ["paytm", "phonepe", "amazonpay", "mobikwik"]
UPI_HANDLES = ["okhdfcbank", "oksbi", "okicici", "okaxis", "ybl", "paytm"]
FAILURE_REASONS = [
    ("BAD_REQUEST_ERROR", "Payment failed due to insufficient funds"),
    ("GATEWAY_ERROR", "Card was declined by the issuing bank"),
    ("BAD_REQUEST_ERROR", "Payment failed due to incorrect OTP"),
]


def _random_id(prefix: str, length: int = 14) -> str:
    chars = string.ascii_letters + string.digits
    return prefix + "".join(random.choices(chars, k=length))


def _method_specific_fields(method: str, fake: Faker) -> dict:
    """Only one of card_id/bank/wallet/vpa is populated, matching the real API
    (Razorpay sets the field for whichever method was used, nulls the rest)."""
    fields = {"card_id": None, "bank": None, "wallet": None, "vpa": None}
    if method == "card":
        fields["card_id"] = _random_id("card_")
    elif method == "netbanking":
        fields["bank"] = random.choice(BANKS)
    elif method == "wallet":
        fields["wallet"] = random.choice(WALLETS)
    elif method == "upi":
        fields["vpa"] = f"{fake.user_name()}@{random.choice(UPI_HANDLES)}"
    return fields


def generate_payments(n: int = 80, start_date: datetime | None = None, seed: int = 42) -> list[dict]:
    """Generate n synthetic payments matching Razorpay's real Payment entity shape.

    Amount is in paise (integer) and created_at is a Unix timestamp (integer
    seconds), both matching Razorpay's real API conventions.
    """
    random.seed(seed)
    fake = Faker()
    Faker.seed(seed)

    start_date = start_date or (datetime.now(timezone.utc) - timedelta(days=30))

    payments = []
    for _ in range(n):
        amount_rupees = round(random.uniform(150, 25000), 2)
        amount_paise = int(round(amount_rupees * 100))
        created_at_dt = start_date + timedelta(
            days=random.randint(0, 29),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        status = random.choice(STATUSES)
        captured = status in ("captured", "refunded")
        fee_paise = int(round(amount_paise * 0.02)) if captured else 0
        tax_paise = int(round(fee_paise * 0.18))  # GST on the fee, like Razorpay's real fee structure

        error_code, error_description = (None, None)
        if status == "failed":
            error_code, error_description = random.choice(FAILURE_REASONS)

        vendor = fake.company()
        method = random.choice(METHODS)

        payments.append({
            "id": _random_id("pay_"),
            "entity": "payment",
            "amount": amount_paise,
            "currency": "INR",
            "status": status,
            "order_id": _random_id("order_"),
            "invoice_id": None,
            "international": False,
            "method": method,
            "amount_refunded": amount_paise if status == "refunded" else 0,
            "refund_status": "full" if status == "refunded" else None,
            "captured": captured,
            "description": f"Payment for {vendor}",
            **_method_specific_fields(method, fake),
            "email": fake.company_email(),
            "contact": fake.phone_number(),
            "notes": {},
            "fee": fee_paise,
            "tax": tax_paise,
            "error_code": error_code,
            "error_description": error_description,
            "created_at": int(created_at_dt.timestamp()),
        })

    return payments


def generate_settlements(payments: list[dict], seed: int = 42, settlement_lag_days: int = 2) -> list[dict]:
    """Batch captured payments into daily settlement records, matching
    Razorpay's real Settlement entity shape.

    Real Razorpay settlements batch a day's captured payments together, net
    of fees/tax, and pay out ~T+2 days later with a bank UTR reference. This
    isn't wired into the matching engine yet (that reconciles at the
    payment level) — it's provided as a second authentic data source for
    the "Payments/Settlements" pairing the buildathon brief mentions.
    """
    random.seed(seed + 1)  # different stream from generate_payments

    batches: dict[str, list[dict]] = {}
    for p in payments:
        if not p["captured"]:
            continue
        day_key = datetime.fromtimestamp(p["created_at"], tz=timezone.utc).date().isoformat()
        batches.setdefault(day_key, []).append(p)

    settlements = []
    for day_key, batch in sorted(batches.items()):
        gross = sum(p["amount"] for p in batch)
        fees = sum(p["fee"] for p in batch)
        tax = sum(p["tax"] for p in batch)
        settled_date = datetime.fromisoformat(day_key).replace(tzinfo=timezone.utc) + timedelta(
            days=settlement_lag_days
        )
        settlements.append({
            "id": _random_id("setl_"),
            "entity": "settlement",
            "amount": gross - fees - tax,
            "status": "processed",
            "fees": fees,
            "tax": tax,
            "utr": "".join(random.choices(string.digits, k=12)),
            "created_at": int(settled_date.timestamp()),
        })

    return settlements
