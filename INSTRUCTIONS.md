
# LCSC Orders Tracker

> I wrote this repository to solve the pain of ordering a lot of electronic components and then not knowing if I had ordered them before. I also use this to share with other laboratory members for quick searching and to help them use these parts in their designs.

This project automatically combines all CSV order files in the `orders` folder, removes unnecessary columns, and generates a Markdown table with LCSC links in the `README.md`.

## How to Use

### 1. Clone the Repository
```sh
git clone https://github.com/leybme/lcsc-orders-tracker.git
cd lcsc-orders-tracker
```


### 2. Download and Add Your CSV Files

You can download your order CSV files from LCSC by following these steps:

1. Go to [https://www.lcsc.com/order/list](https://www.lcsc.com/order/list) and log in to your account.
2. Find the order you want to export.
3. Click the **Export BOM** button for that order.
4. Save the downloaded CSV file to your computer.
5. Move or copy the CSV file into the `orders` directory of this repository (create it if it doesn't exist).

### 3. Run the Update Script
Make sure you have Python 3.7+ and pandas installed:
```sh
pip install pandas
python update.py
```

- This will generate/refresh `combined.csv` and `README.md` in the root directory.


### 4. GitHub Actions (Optional)
- The repository includes a GitHub Actions workflow that will automatically run the update script and update the README whenever you push new CSV files or make any commit.

#### Set GitHub Actions Token Permissions
To allow the workflow to push changes (such as updating README.md) back to the repository, make sure the workflow token has write permissions:

1. Go to your repository on GitHub.
2. Click on **Settings** > **Actions** > **General**.
3. Scroll down to **Workflow permissions**.
4. Select **Read and write permissions** for the GITHUB_TOKEN.
5. Click **Save**.

This ensures the workflow can commit and push changes automatically.

## Notes
- The script removes the columns: `Customer NO.`, `Date Code / Lot No.`, and `Estimated lead time (business days)`.
- The column `Manufacture Part Number` is renamed to `MPN`.
- The `Description` column is moved to the third position.
- The `LCSC Part Number` column is rendered as a clickable link in the Markdown table.

---

Feel free to open issues or pull requests for improvements!
