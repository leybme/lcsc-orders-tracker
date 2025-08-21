import pandas as pd
import glob
import os

# Set the directory containing your CSV files
csv_dir = r'd:\LCSC'

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

# Save to a new CSV file
combined_df.to_csv(os.path.join(csv_dir, 'combined.csv'), index=False)