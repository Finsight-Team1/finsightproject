
from pathlib import Path
import pandas as pd

# FinSight data-cleaning script

# Look for CSV files in the project folder
finsightproject = Path(__file__).resolve().parent

csv_files = list(finsightproject.glob("*.csv"))

if not csv_files:
    print("No CSV files found in the project folder.")
    print("Please check where your dataset is saved.")

else:
    print("CSV files found:")

    for index, file in enumerate(csv_files, start=1):
        print(f"{index}. {file.name}")

    # Load the first CSV file
    dataset_path = csv_files[0]
    df = pd.read_csv(dataset_path)

    print("\nSelected dataset:", dataset_path.name)
    print("Dataset shape:", df.shape)

    print("\nColumn names:")
    print(df.columns.tolist())

    print("\nFirst 5 rows:")
    print(df.head())

    print("\nMissing values per column:")
    print(df.isnull().sum())

    print("\nExact duplicate rows:", df.duplicated().sum())
    
    
    
    print("\n--- DATA TYPES ---")
    print(df.dtypes)

    print("\n--- ALL COLUMN NAMES ---")
    for number, column in enumerate(df.columns, start=1):
        print(f"Column {number}: {column}")

    print("\n--- INDUSTRIES ---")
    if "industry" in df.columns:
        print(df["industry"].value_counts(dropna=False))
    else:
        print("No column named 'industry' found.")

    print("\n--- TRANSACTION STATUS ---")
    if "status" in df.columns:
        print(df["status"].value_counts(dropna=False))
    elif "transaction_status" in df.columns:
        print(df["transaction_status"].value_counts(dropna=False))
    else:
        print("No obvious transaction status column found.")
        
        

from pathlib import Path
import pandas as pd

# ==========================================
# FINSIGHT: DATA CLEANING
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "finsight_complete_sme_transactions.csv"
OUTPUT_FILE = BASE_DIR / "finsight_cleaned.csv"
REVIEW_FILE = BASE_DIR / "data_quality_report.csv"

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Dataset not found: {INPUT_FILE.name}\n"
        "Place the original CSV in the same folder as clean_data.py."
    )

# Load the original dataset
df = pd.read_csv(INPUT_FILE)

original_rows = len(df)

print("=" * 50)
print("FINSIGHT DATA CLEANING")
print("=" * 50)
print(f"Original rows: {original_rows}")
print(f"Original columns: {len(df.columns)}")

# 1. Standardise column names
df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace(" ", "_")
)

# 2. Clean whitespace in text columns
for column in df.select_dtypes(include=["object", "str"]).columns:
    df[column] = df[column].map(
        lambda value: value.strip()
        if isinstance(value, str) else value
    )

# Convert empty strings to missing values in optional fields
optional_fields = [
    "related_transaction_id",
    "duplicate_of_transaction_id",
    "counterparty",
    "opening_balance_ngn",
    "closing_balance_ngn",
    "anomaly_type",
]

for column in optional_fields:
    if column in df.columns:
        df[column] = df[column].replace("", pd.NA)

# 3. Standardise industry labels
if "industry" in df.columns:
    df["industry"] = df["industry"].str.strip()

    industry_mapping = {
        "hospitality": "Hospitality",
        "fashion & apparel": "Fashion & Apparel",
        "agribusiness": "Agribusiness",
        "retail": "Retail",
        "manufacturing": "Manufacturing",
        "tech startups": "Tech Startups",
    }

    df["industry"] = df["industry"].map(
        lambda value: industry_mapping.get(
            value.lower(), value
        ) if isinstance(value, str) else value
    )

# 4. Convert date/time fields
if "datetime" in df.columns:
    df["datetime"] = pd.to_datetime(
        df["datetime"], errors="coerce"
    )

if "date" in df.columns:
    df["date"] = pd.to_datetime(
        df["date"], errors="coerce"
    )

# 5. Convert numeric fields safely
numeric_columns = [
    "amount",
    "cash_inflow_ngn",
    "cash_outflow_ngn",
    "transfer_in_ngn",
    "transfer_out_ngn",
    "net_cash_movement_ngn",
    "opening_balance_ngn",
    "closing_balance_ngn",
]

for column in numeric_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(
            df[column], errors="coerce"
        )

# 6. Create review flags without deleting records
df["review_required"] = False
df["review_reason"] = ""

def add_review_flag(mask, reason):
    mask = mask.fillna(False)
    df.loc[mask, "review_required"] = True

    existing = df.loc[mask, "review_reason"]
    df.loc[mask, "review_reason"] = existing.map(
        lambda text: f"{text}; {reason}"
        if text else reason
    )

# Required field checks
required_fields = [
    "transaction_id",
    "datetime",
    "sme_id",
    "business_name",
    "industry",
    "amount",
    "type",
    "status",
]

for column in required_fields:
    if column in df.columns:
        add_review_flag(
            df[column].isna(),
            f"Missing {column}"
        )

# Transaction ID checks
if "transaction_id" in df.columns:
    add_review_flag(
        df["transaction_id"].duplicated(keep=False),
        "Duplicate transaction ID"
    )

# Validate industry labels
allowed_industries = {
    "Hospitality",
    "Fashion & Apparel",
    "Agribusiness",
    "Retail",
    "Manufacturing",
    "Tech Startups",
}

if "industry" in df.columns:
    add_review_flag(
        ~df["industry"].isin(allowed_industries),
        "Missing or unrecognised industry"
    )

# Flag negative transaction amounts for review
if "amount" in df.columns:
    add_review_flag(
        df["amount"] < 0,
        "Negative amount; verify transaction convention"
    )

# Flag invalid dates
if "datetime" in df.columns:
    add_review_flag(
        df["datetime"].isna(),
        "Invalid or missing datetime"
    )

# Validate synthetic anomaly labels
if "is_synthetic_anomaly" in df.columns:
    add_review_flag(
        ~df["is_synthetic_anomaly"].isin([0, 1]),
        "Invalid synthetic anomaly label"
    )

# Flag failed transactions for review, but retain them
if "status" in df.columns:
    failed = (
        df["status"].astype("string").str.lower()
        == "failed"
    )
    add_review_flag(
        failed,
        "Failed transaction; exclude from completed cash totals"
    )

# Flag missing counterparties without deleting rows
if "counterparty" in df.columns:
    add_review_flag(
        df["counterparty"].isna(),
        "Missing counterparty"
    )

# 7. Save the cleaned master dataset
# No rows are automatically deleted.
df.to_csv(OUTPUT_FILE, index=False)

# 8. Save only records flagged for review
review_df = df[df["review_required"]].copy()
review_df.to_csv(REVIEW_FILE, index=False)

# 9. Print validation summary
print("\nCLEANING SUMMARY")
print("-" * 40)
print(f"Rows retained: {len(df)}")
print(f"Rows removed: {original_rows - len(df)}")
print(f"Rows needing review: {len(review_df)}")

print("\nIndustry counts:")
print(df["industry"].value_counts(dropna=False))

print("\nTransaction status counts:")
print(df["status"].value_counts(dropna=False))

print("\nMissing values after cleaning:")
print(df.isna().sum().to_string())

print("\nFiles created:")
print(OUTPUT_FILE.name)
print(REVIEW_FILE.name)

print("\nCleaning completed.")


import pandas as pd
from pathlib import Path

# Define the project directory
BASE_DIR = Path(__file__).resolve().parent

# Input: cleaned master dataset
INPUT_FILE = BASE_DIR / "finsight_cleaned.csv"

# Output directory for industry-specific datasets
OUTPUT_DIR = BASE_DIR / "industry_data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load the cleaned master dataset
df = pd.read_csv(INPUT_FILE)

# Normalize column names for easier matching
df.columns = df.columns.str.strip()

# Industry names and their corresponding output files
INDUSTRY_FILES = {
    "retail": "retail.csv",
    "hospitality": "hospitality.csv",
    "agribusiness": "agribusiness.csv",
    "fashion_apparel": "fashion_apparel.csv",
    "manufacturing": "manufacturing.csv",
    "tech_startups": "tech_startups.csv",
}

# Find the industry column
possible_columns = [
    "industry",
    "industry_type",
    "business_industry",
    "sector",
]

industry_column = next(
    (
        col for col in df.columns
        if col.strip().lower() in possible_columns
    ),
    None,
)

if industry_column is None:
    raise ValueError(
        "No industry column found. "
        f"Available columns: {df.columns.tolist()}"
    )

# Standardize industry labels for matching
industry_values = (
    df[industry_column]
    .astype("string")
    .str.strip()
    .str.lower()
    .str.replace(r"[\s\-&]+", "_", regex=True)
)

# Support common alternative industry labels
INDUSTRY_ALIASES = {
    "retail": {"retail", "retail_trade"},
    "hospitality": {
        "hospitality",
        "hotel",
        "hotels",
        "tourism",
        "food_service",
        "food_and_beverage",
    },
    "agribusiness": {
        "agribusiness",
        "agriculture",
        "agricultural",
        "agriculture_and_farming",
    },
    "fashion_apparel": {
        "fashion_apparel",
        "fashion",
        "apparel",
        "fashion_and_apparel",
        "clothing",
    },
    "manufacturing": {
        "manufacturing",
        "manufacturer",
        "industrial_manufacturing",
    },
    "tech_startups": {
        "tech_startups",
        "tech",
        "technology",
        "technology_startups",
        "tech_startup",
        "information_technology",
        "it",
    },
}

# Split and save each industry
for industry, filename in INDUSTRY_FILES.items():
    aliases = INDUSTRY_ALIASES[industry]

    industry_df = df[industry_values.isin(aliases)].copy()

    output_file = OUTPUT_DIR / filename
    industry_df.to_csv(output_file, index=False)

    print(
        f"{industry}: {len(industry_df):,} records saved to "
        f"{output_file}"
    )

# Report unmatched labels so they can be corrected if necessary
recognized_labels = set().union(*INDUSTRY_ALIASES.values())
unmatched_mask = (
    industry_values.notna()
    & industry_values.ne("")
    & ~industry_values.isin(recognized_labels)
)

unmatched_labels = sorted(
    industry_values.loc[unmatched_mask].unique().tolist()
)

print("\nIndustry splitting completed.")
print(f"Master records: {len(df):,}")
print(f"Master file preserved: {INPUT_FILE}")

if unmatched_labels:
    print("\nWARNING: Unmatched industry labels found:")
    for label in unmatched_labels:
        print(f"  - {label}")
    print("Review these labels before relying on the split datasets.")
else:
    print("All non-empty industry labels were recognized.")

# ==========================================
# FINAL VALIDATION CHECKS
# ==========================================

print("\nFINAL VALIDATION")
print("-" * 40)

# Check transaction ID uniqueness
print(
    "Unique transaction IDs:",
    df["transaction_id"].nunique()
)
print("Total transaction rows:", len(df))

# Check valid datetime values
print(
    "Invalid datetime values:",
    df["datetime"].isna().sum()
)

# Check negative amounts
print(
    "Negative amounts:",
    (df["amount"] < 0).sum()
)

# Check anomaly label values
print(
    "Anomaly label counts:"
)
print(df["is_synthetic_anomaly"].value_counts())

# Check completed and failed transactions
print("\nStatus by cash movement status:")
print(
    pd.crosstab(
        df["status"],
        df["cash_movement_status"],
        dropna=False
    )
)

# Check net cash movement calculation
expected_net = (
    df["cash_inflow_ngn"] - df["cash_outflow_ngn"]
)

mismatch = (
    (df["net_cash_movement_ngn"] - expected_net).abs()
    > 0.01
)

print(
    "\nRows where net cash movement differs from "
    "inflow minus outflow:",
    mismatch.sum()
)