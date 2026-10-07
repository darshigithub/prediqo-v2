# Generated sample e-commerce dataset (50 rows, 18 columns)
# Used by the AI Analytics Prototype acceptance test
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "uploads"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "ecommerce_sales.csv"

CITIES = [
    ("Mumbai", "Maharashtra"), ("Delhi", "Delhi"), ("Bengaluru", "Karnataka"),
    ("Hyderabad", "Telangana"), ("Chennai", "Tamil Nadu"), ("Pune", "Maharashtra"),
    ("Kolkata", "West Bengal"), ("Jaipur", "Rajasthan"),
]
CATEGORIES = {
    "Electronics": ["Smartphone", "Laptop", "Headphones", "Smart Watch", "Tablet"],
    "Furniture": ["Office Chair", "Study Table", "Bookshelf", "Sofa", "Bed Frame"],
    "Clothing": ["T-Shirt", "Jeans", "Kurta", "Jacket", "Saree"],
    "Grocery": ["Basmati Rice 5kg", "Olive Oil 1L", "Almonds 500g", "Green Tea", "Honey 500g"],
}
PAYMENTS = ["UPI", "Credit Card", "Debit Card", "Net Banking", "Cash on Delivery"]
CHANNELS = ["Google Ads", "Instagram", "Email", "Organic Search", "Referral"]
STATUSES = ["Completed", "Completed", "Completed", "Completed", "Shipped", "Pending", "Cancelled"]
GENDERS = ["Male", "Female", "Other"]

rows = []
start = date(2025, 1, 1)
for i in range(1, 51):
    city, state = random.choice(CITIES)
    category = random.choice(list(CATEGORIES))
    product = random.choice(CATEGORIES[category])
    order_date = start + timedelta(days=random.randint(0, 270))
    quantity = random.randint(1, 5)
    price = {
        "Electronics": random.randint(4999, 89999),
        "Furniture": random.randint(1999, 39999),
        "Clothing": random.randint(499, 4999),
        "Grocery": random.randint(99, 1999),
    }[category]
    discount = random.choice([0, 0, 5, 10, 15, 20])
    total = round(quantity * price * (100 - discount) / 100, 2)
    rows.append([
        f"ORD-{1000 + i}",                      # Order_ID
        order_date.isoformat(),                 # Order_Date
        f"CUST-{random.randint(100, 149)}",     # Customer_ID
        random.randint(18, 65),                 # Customer_Age
        random.choice(GENDERS),                 # Gender
        city,                                   # City
        state,                                  # State
        category,                               # Product_Category
        product,                                # Product
        quantity,                               # Quantity
        price,                                  # Unit_Price
        discount,                               # Discount_Percent
        random.choice(PAYMENTS),                # Payment_Method
        random.randint(1, 9),                   # Delivery_Days
        round(random.uniform(2.5, 5.0), 1),     # Customer_Rating
        random.choice(CHANNELS),                # Marketing_Channel
        random.choice(STATUSES),                # Order_Status
        total,                                  # Total_Amount
    ])

HEADERS = [
    "Order_ID", "Order_Date", "Customer_ID", "Customer_Age", "Gender", "City", "State",
    "Product_Category", "Product", "Quantity", "Unit_Price", "Discount_Percent",
    "Payment_Method", "Delivery_Days", "Customer_Rating", "Marketing_Channel",
    "Order_Status", "Total_Amount",
]

with OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(HEADERS)
    w.writerows(rows)

print(f"Wrote {len(rows)} rows x {len(HEADERS)} columns -> {OUT}")
