import pandas as pd

xlsx_path = "Police force in England.xlsx"
df = pd.read_excel(xlsx_path, sheet_name="Territorial Forces")
print(df.iloc[2:10].to_string())
