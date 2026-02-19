import pandas as pd
import glob
import os
import re
from datetime import datetime


# Set root and the directory containing your CSV files (relative path for portability)
root_dir = os.path.dirname(__file__)
csv_dir = os.path.join(root_dir, 'orders')



def _parse_order_date(order_number: str) -> str:
    """Derive order date from order number (WMYYMMDDxxxx -> 20YY-MM-DD)."""
    m = re.match(r'^WM(\d{2})(\d{2})(\d{2})', order_number)
    if m:
        yy, mm, dd = m.groups()
        return f"20{yy}-{mm}-{dd}"
    return 'Unknown'

# Find all CSV files in the directory
csv_files = glob.glob(os.path.join(csv_dir, '*.csv'))

# List to hold DataFrames and order metadata
dfs = []
orders_info = []

# Loop through files and read them
for i, file in enumerate(csv_files):
    if i == 0:
        # Read header for the first file
        df = pd.read_csv(file)
    else:
        # Skip header for subsequent files
        df = pd.read_csv(file, header=0)
    
    # Extract date from filename: LCSC__WM2310150097_20250821103144.csv -> 20250821
    filename = os.path.basename(file)
    match = re.match(r'^LCSC__([A-Z0-9]+)_(\d{8})\d+\.csv$', filename)
    if match:
        order_number = match.group(1)
        # Prefer parsing date from order number (first date), fallback to filename timestamp
        order_date = _parse_order_date(order_number)
        if order_date == 'Unknown':
            date_str = match.group(2)
            order_date = datetime.strptime(date_str, '%Y%m%d').strftime('%Y-%m-%d')
        df['Last Update'] = order_date
        # Compute total value for this order
        if 'Ext.Price($)' in df.columns and pd.api.types.is_numeric_dtype(df['Ext.Price($)']):
            order_total = float(df['Ext.Price($)'].sum())
        else:
            order_total = float((df['Quantity'] * df['Unit Price($)']).sum())
        orders_info.append({
            'Order #': order_number,
            'Last Update': order_date,
            'Source File': filename,
            'Total Value($)': round(order_total, 2),
        })
    else:
        df['Last Update'] = 'Unknown'
        orders_info.append({
            'Order #': 'Unknown',
            'Last Update': 'Unknown',
            'Source File': filename,
            'Total Value($)': 0.0,
        })
    
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

# Keep 'Manufacture Part Number' as a separate column, and also create 'MPN' for merging and display
if 'Manufacture Part Number' in combined_df.columns:
    combined_df['MPN'] = combined_df['Manufacture Part Number']



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
    if 'Last Update' in combined_df.columns:
        agg_dict['Last Update'] = 'max'  # Keep the most recent date

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


# Sort by Package and MPN
sort_cols = []
if 'Package' in combined_df.columns:
    sort_cols.append('Package')
if 'MPN' in combined_df.columns:
    sort_cols.append('MPN')
if sort_cols:
    combined_df = combined_df.sort_values(by=sort_cols, na_position='last')

# Reorder columns: LCSC Part Number, Manufacture Part Number, MPN, Description, Package, Manufacturer, then the rest
first_cols = ['LCSC Part Number', 'Manufacture Part Number', 'MPN', 'Description', 'Package', 'Manufacturer']
cols = [col for col in first_cols if col in combined_df.columns] + [col for col in combined_df.columns if col not in first_cols]
combined_df = combined_df[cols]

# Save to a new CSV file
combined_df.to_csv(os.path.join(root_dir, 'combined.csv'), index=False)

# Build order list (deduped by order number, newest first) and save to CSV
orders_df = pd.DataFrame(orders_info)
orders_table_md = ''
if not orders_df.empty:
    if 'Last Update' in orders_df.columns:
        # Coerce to datetime where possible for sorting
        orders_df['Last Update'] = pd.to_datetime(orders_df['Last Update'], errors='coerce')
    orders_df = orders_df.sort_values(['Last Update', 'Order #'], ascending=[False, True])
    # Keep the newest record per order number
    if 'Order #' in orders_df.columns:
        orders_df = orders_df.drop_duplicates(subset=['Order #'], keep='first')
    # Format date back to string for output
    if 'Last Update' in orders_df.columns:
        orders_df['Last Update'] = orders_df['Last Update'].dt.strftime('%Y-%m-%d')

    orders_df.to_csv(os.path.join(root_dir, 'orderlist.csv'), index=False)

    # Markdown table for orders
    orders_header = '| ' + ' | '.join(orders_df.columns) + ' |\n'
    orders_separator = '| ' + ' | '.join(['---'] * len(orders_df.columns)) + ' |\n'
    order_rows = ''
    for _, row in orders_df.iterrows():
        cells = []
        for col in orders_df.columns:
            val = row[col]
            if col == 'Total Value($)':
                cells.append(f"${val:.2f}")
            else:
                cells.append(str(val))
        order_rows += '| ' + ' | '.join(cells) + ' |\n'
    orders_table_md = '## Orders\n\n' + orders_header + orders_separator + order_rows + '\n'
else:
    orders_table_md = '## Orders\n\n_No orders found._\n\n'

# Column name for LCSC Part Number
part_col = 'LCSC Part Number'

# Generate Markdown table headerC62892,UMH3N,"100@1mA,5V 150mW 100mA 50V SOT-363 Digital Transistors ROHS","Jiangsu Changjing Electronics Technology Co., Ltd.",SOT-363,YES,10,0.0477,0.48,-

# Ensure Markdown table uses the new column order
header = '| ' + ' | '.join(combined_df.columns) + ' |\n'
separator = '| ' + ' | '.join(['---'] * len(combined_df.columns)) + ' |\n'


# Generate Markdown table rows with links for LCSC Part Number and Manufacturer (datasheet)
rows = ''
for _, row in combined_df.iterrows():
    row_cells = []
    datasheet_url = ''
    if part_col in row and pd.notna(row[part_col]) and str(row[part_col]).strip():
        datasheet_url = f'https://www.lcsc.com/datasheet/{row[part_col]}.pdf'
    for col in combined_df.columns:
        cell = str(row[col])
        if col == part_col and pd.notna(cell) and cell.strip():
            cell = f'[{cell}](https://www.lcsc.com/product-detail/{cell}.html)'
        elif col == 'Manufacture Part Number' and datasheet_url:
            cell = f'[{cell}]({datasheet_url})'
        row_cells.append(cell)
    rows += '| ' + ' | '.join(row_cells) + ' |\n'

# Calculate summary information
total_items = len(combined_df)
total_quantity = combined_df[qty_col].sum() if qty_col in combined_df.columns else 0
total_value = combined_df[ext_price_col].sum() if ext_price_col in combined_df.columns else 0

# Create summary section
summary = f'''## Summary

- **Total Items**: {total_items}
- **Total Quantity**: {int(total_quantity)}MPN
- **Total Value**: ${total_value:.2f}

---

'''

# Combine all parts
markdown = '# Materials List\n\n' + orders_table_md + summary + header + separator + rows


# Write to README.md in the root directory
with open(os.path.join(root_dir, 'README.md'), 'w', encoding='utf-8') as f:
    f.write(markdown)



print('combined.csv and README.md with links generated successfully.')
