import pandas as pd

xlsx_path = "Police force in England.xlsx"
df = pd.read_excel(xlsx_path, sheet_name="Territorial Forces")
pd.set_option('display.max_rows', 100)
print(df)
