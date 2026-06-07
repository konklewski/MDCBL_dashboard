import pandas as pd

xlsx_path = "Police force in England.xlsx"
xl = pd.ExcelFile(xlsx_path)
print("Sheet Names:", xl.sheet_names)

for name in xl.sheet_names:
    print(f"\n--- FULL SHEET: {name} ---")
    df = pd.read_excel(xlsx_path, sheet_name=name)
    print("Shape:", df.shape)
    print("Columns:", df.columns.tolist())
    print(df.head(20))
