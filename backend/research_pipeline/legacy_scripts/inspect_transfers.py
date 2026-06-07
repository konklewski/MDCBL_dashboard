import pandas as pd

# Load the transfers DataFrame from a quick run or re-run the final part
# We will just write a python script that runs the LP part and prints to string
import test_reallocation_model
print("\n--- Printing Top 15 optimized transfers in full ---")
print(test_reallocation_model.df_transfers.head(15).to_string())
