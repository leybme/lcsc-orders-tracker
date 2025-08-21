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

# Move 'Description' column to the third position if it exists
cols = list(combined_df.columns)
if 'Description' in cols:
    cols.remove('Description')
    cols.insert(2, 'Description')
    combined_df = combined_df[cols]

# Save to a new CSV file
combined_df.to_csv(os.path.join(csv_dir, 'combined.csv'), index=False)

# Column name for LCSC Part Number
part_col = 'LCSC Part Number'

# Generate Markdown table header
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
