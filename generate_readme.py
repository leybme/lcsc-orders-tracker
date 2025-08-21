import pandas as pd
import os

# Path to the combined CSV file
data_path = 'combined.csv'

# Read the combined CSV file
df = pd.read_csv(data_path)

# Column name for LCSC Part Number
part_col = 'LCSC Part Number'

# Columns to remove
cols_to_remove = [
    'Customer NO.',
    'Date Code / Lot No.',
    'Estimated lead time (business days)'
]

# Drop the specified columns if they exist
df = df.drop(columns=[col for col in cols_to_remove if col in df.columns])

# Generate Markdown table header
header = '| ' + ' | '.join(df.columns) + ' |\n'
separator = '| ' + ' | '.join(['---'] * len(df.columns)) + ' |\n'

# Generate Markdown table rows with links for LCSC Part Number
rows = ''
for _, row in df.iterrows():
    row_cells = []
    for col in df.columns:
        cell = str(row[col])
        if col == part_col and pd.notna(cell) and cell.strip():
            cell = f'[{cell}](https://www.lcsc.com/product-detail/{cell}.html)'
        row_cells.append(cell)
    rows += '| ' + ' | '.join(row_cells) + ' |\n'

# Combine all parts
markdown = '# Materials List\n\n' + header + separator + rows

# Write to README.md
with open('README.md', 'w', encoding='utf-8') as f:
    f.write(markdown)

print('README.md with links generated successfully.')
