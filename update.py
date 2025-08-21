import pandas as pd
import glob
import os


# Set the directory containing your CSV files (relative path for portability)
csv_dir = os.path.join(os.path.dirname(__file__), 'orders')

# Find all CSV files in the directory
csv_files = glob.glob(os.path.join(csv_dir, '*.csv'))

# List to hold DataFrames
dfs = []

# Loop through files and read them
for i, file in enumerate(csv_files):
    if i == 0:
        # Read header for the first file
        df = pd.read_csv(file)
    else:
        # Skip header for subsequent files
        df = pd.read_csv(file, header=0)
    dfs.append(df)

# Concatenate all DataFrames
combined_df = pd.concat(dfs, ignore_index=True)


# Columns to remove
cols_to_remove = [
    'Customer NO.',
    'Date Code / Lot No.',
    'Estimated lead time (business days)'
]
combined_df = combined_df.drop(columns=[col for col in cols_to_remove if col in combined_df.columns])

# Rename 'Manufacture Part Number' to 'MPN' if it exists
if 'Manufacture Part Number' in combined_df.columns:
    combined_df = combined_df.rename(columns={'Manufacture Part Number': 'MPN'})



# Move 'Description' column to the third position if it exists
cols = list(combined_df.columns)
if 'Description' in cols:
    cols.remove('Description')
    cols.insert(2, 'Description')
    combined_df = combined_df[cols]


# Merge duplicate items by 'LCSC Part Number'
part_col = 'LCSC Part Number'
qty_col = 'Quantity'
price_col = 'Unit Price($)'
ext_price_col = 'Ext.Price($)'
desc_col = 'Description'
mpn_col = 'MPN'


if part_col in combined_df.columns:
    print("\n[DEBUG] Checking for duplicates before merge...")
    dupes = combined_df[combined_df.duplicated(subset=[part_col], keep=False)]
    if not dupes.empty:
        print(f"[DEBUG] Found {dupes[part_col].nunique()} unique duplicate part numbers.")
        print(dupes[[part_col, qty_col, price_col, ext_price_col, desc_col, mpn_col]].to_string(index=False))
    else:
        print("[DEBUG] No duplicates found.")

    agg_dict = {}
    if qty_col in combined_df.columns:
        agg_dict[qty_col] = 'sum'
    if price_col in combined_df.columns:
        agg_dict[price_col] = 'max'
    if ext_price_col in combined_df.columns:
        agg_dict[ext_price_col] = 'sum'
    if desc_col in combined_df.columns:
        agg_dict[desc_col] = 'first'
    if mpn_col in combined_df.columns:
        agg_dict[mpn_col] = 'first'

    merged_df = combined_df.groupby(part_col, as_index=False).agg(agg_dict)

    # If ext_price_col not present, calculate it
    if ext_price_col in merged_df.columns and qty_col in merged_df.columns and price_col in merged_df.columns:
        merged_df[ext_price_col] = (merged_df[qty_col] * merged_df[price_col]).round(2)
    elif qty_col in merged_df.columns and price_col in merged_df.columns:
        merged_df[ext_price_col] = (merged_df[qty_col] * merged_df[price_col]).round(2)

    # Re-add any columns not aggregated
    for col in combined_df.columns:
        if col not in merged_df.columns and col != part_col:
            merged_df[col] = combined_df.groupby(part_col)[col].first().values

    print("\n[DEBUG] After merge, merged items:")
    print(merged_df[[part_col, qty_col, price_col, ext_price_col, desc_col, mpn_col]].to_string(index=False))

    combined_df = merged_df


# Reorder columns: LCSC Part Number, MPN, Description, Package, Manufacturer, then the rest
first_cols = ['LCSC Part Number', 'MPN', 'Description', 'Package', 'Manufacturer']
cols = [col for col in first_cols if col in combined_df.columns] + [col for col in combined_df.columns if col not in first_cols]
combined_df = combined_df[cols]

# Save to a new CSV file
combined_df.to_csv(os.path.join(os.path.dirname(__file__), 'combined.csv'), index=False)

# Column name for LCSC Part Number
part_col = 'LCSC Part Number'

# Generate Markdown table headerC62892,UMH3N,"100@1mA,5V 150mW 100mA 50V SOT-363 Digital Transistors ROHS","Jiangsu Changjing Electronics Technology Co., Ltd.",SOT-363,YES,10,0.0477,0.48,-

# Ensure Markdown table uses the new column order
header = '| ' + ' | '.join(combined_df.columns) + ' |\n'
separator = '| ' + ' | '.join(['---'] * len(combined_df.columns)) + ' |\n'

# Generate Markdown table rows with links for LCSC Part Number
rows = ''
for _, row in combined_df.iterrows():
    row_cells = []
    for col in combined_df.columns:
        cell = str(row[col])
        if col == part_col and pd.notna(cell) and cell.strip():
            cell = f'[{cell}](https://www.lcsc.com/product-detail/{cell}.html)'
        row_cells.append(cell)
    rows += '| ' + ' | '.join(row_cells) + ' |\n'

# Combine all parts
markdown = '# Materials List\n\n' + header + separator + rows


# Write to README.md in the root directory
root_dir = os.path.dirname(__file__)
with open(os.path.join(root_dir, 'README.md'), 'w', encoding='utf-8') as f:
    f.write(markdown)



print('combined.csv and README.md with links generated successfully.')
