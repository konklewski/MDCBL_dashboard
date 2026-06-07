import pandas as pd

for pf in ["data/stop_and_searchfrom_2018.parquet", "data/stop_and_search_from_2021.parquet"]:
    print(f"\n--- Reading {pf} ---")
    # Read just a subset of columns or read and take head
    df = pd.read_parquet(pf).head(5)
    print("Columns:", df.columns.tolist())
    print(df)
