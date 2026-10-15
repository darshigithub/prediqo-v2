
import pandas as pd
from pathlib import Path

# Dataset folder
folder = Path(r"C:\Users\Darshan\Videos\prediqo-v2")

# Input and output files
input_file = folder / "ecommerce_orders_dataset.csv"
output_file = folder / "ecommerce_orders_dataset_cleaned.csv"

# Keep records up to October 15, 2026
cutoff_date = pd.Timestamp("2026-10-15 23:59:59")

# Load CSV
df = pd.read_csv(input_file)

# Parse dates
df["Order_Date"] = pd.to_datetime(
    df["Order_Date"], errors="coerce"
)

# Remove missing, invalid, and future dates
cleaned_df = df[
    df["Order_Date"].notna()
    & (df["Order_Date"] <= cutoff_date)
].copy()

# Save without overwriting the original
cleaned_df.to_csv(output_file, index=False)

print("Cleaning completed successfully!")
print(f"Original rows: {len(df):,}")
print(f"Cleaned rows: {len(cleaned_df):,}")
print(f"Removed rows: {len(df) - len(cleaned_df):,}")
print(f"Output file: {output_file}")
