"""Generates synthetic Razorpay-style payment transactions.

This is a stand-in for the real Razorpay test-mode API connector. Field names
and shapes mirror the real Razorpay Payments API entity, so the rest of the
pipeline (matching engine, dashboard) doesn't need to change when this is
swapped for live API data later.
"""

import random
import string
from datetime import datetime, timedelta

from faker import Faker

METHODS = ["card", "upi", "netbanking", "wallet"]
# Weighted so most payments succeed, some fail/refund, like a real gateway.
STATUSES = ["captured", "captured", "captured", "captured", "failed", "refunded"]


def _random_id(prefix: str, length: int = 14) -> str:
    chars = string.ascii_letters + string.digits
    return prefix + "".join(random.choices(chars, k=length))


def generate_transactions(n: int = 80, start_date: datetime | None = None, seed: int = 42) -> list[dict]:
    """Generate n synthetic gateway transactions, structured like Razorpay Payment objects.

    Amount is in paise (integer), matching Razorpay's smallest-currency-unit convention.
    """
    random.seed(seed)
    fake = Faker()
    Faker.seed(seed)

    start_date = start_date or (datetime.now() - timedelta(days=30))

    transactions = []
    for _ in range(n):
        amount_rupees = round(random.uniform(150, 25000), 2)
        amount_paise = int(round(amount_rupees * 100))
        created_at = start_date + timedelta(
            days=random.randint(0, 29),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        status = random.choice(STATUSES)
        fee_paise = int(round(amount_paise * 0.02)) if status == "captured" else 0
        tax_paise = int(round(fee_paise * 0.18))  # GST on the fee, like Razorpay's real fee structure

        vendor = fake.company()
        transactions.append({
            "payment_id": _random_id("pay_"),
            "order_id": _random_id("order_"),
            "amount": amount_paise,
            "currency": "INR",
            "status": status,
            "method": random.choice(METHODS),
            "description": f"Payment for {vendor}",
            "contact": fake.phone_number(),
            "email": fake.company_email(),
            "created_at": created_at,
            "fee": fee_paise,
            "tax": tax_paise,
            "captured": status == "captured",
        })

    return transactions
