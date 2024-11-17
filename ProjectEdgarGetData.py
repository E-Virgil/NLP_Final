from edgar import Company, set_identity
import pandas as pd
from tqdm import tqdm
import yfinance as yf
import time
import os

def get_assets(tickers: list, start_year: int):
    '''
    This function takes a list of ticker symbols and retrieves the asset values for the given timeframe from SEC EDGAR
    database using the edgartools module.  It saves as a csv file locally and returns the data frame and a list
    of related filing dates.
    :param tickers: list of strings of stock ticker identifiers
    :param start_year: year to begin grabbing filings
    :return: data frame of assets with dates organized including tickers as well as the list of related filing dates
    for each ticker
    '''
    # Initialize an empty list to store DataFrames
    all_data = []
    # Loop through each ticker
    for ticker in tqdm(tickers, desc="Grabbing each ticker's assets..."):
        try:
            # Initialize the Company instance
            company = Company(ticker)

            # Retrieve all 10-Q filings since 2009
            filings = company.get_filings(form="10-Q").filter(date=f"{start_year}-01-01:")

            # Convert filings to a DataFrame and filter for 'Assets' fact
            df = company.get_facts().to_pandas()
            assets_df = df.query("fact == 'Assets' and form == '10-Q'")

            # Drop duplicates and keep the first instance for each reporting period
            filtered_df = assets_df.drop_duplicates(subset='end', keep='first')
            filtered_df = filtered_df.iloc[:, :8]

            # Add the ticker symbol to the DataFrame
            filtered_df["Ticker"] = ticker

            # Convert 'end' column to datetime and set as the index
            filtered_df['end'] = pd.to_datetime(filtered_df['end'])
            filtered_df.set_index('end', inplace=True)

            # Append the filtered data to the all_data list
            all_data.append(filtered_df)

        except Exception as e:
            print(f"An error occurred for ticker {ticker}: {e}")

    # Combine all individual DataFrames into one
    final_df = pd.concat(all_data)

    # Save the final DataFrame to a CSV file
    final_df.to_csv("assets_data.csv")

    # Extract the 'end' dates as a set and sort list
    end_dates_list = sorted(set(final_df.index.strftime('%Y-%m-%d')))

    return final_df, end_dates_list

def get_prices(ordered_end_dates: list, tickers: list):
    '''
    This function gets the prices from yahoo finance using yfinance module for comparative purposes to the assets from
    SEC EDGAR database.  It saves as a csv file locally and returns the data frame.
    :param ordered_end_dates: these are the ordered dates from the SEC filings for comparison as a list of strings
    :param tickers: list of strings of stock ticker identifiers
    :return: data frame of prices with dates organized including tickers
    '''
    # Convert ordered_end_dates to datetime and format as strings (date-only)
    ordered_end_dates = pd.to_datetime(ordered_end_dates).strftime('%Y-%m-%d')

    # Get the minimum and maximum dates from the ordered list
    min_date = ordered_end_dates.min()
    max_date = ordered_end_dates.max()

    # Initialize an empty list to store DataFrame rows
    data_rows = []

    # Loop through each ticker
    for ticker in tqdm(tickers, desc="Grabbing each ticker's prices..."):
        try:
            # Fetch data for the full date range
            data = yf.download(ticker, start=min_date, end=max_date, group_by="ticker", progress=False)

            # Check if data is not empty
            if not data.empty:
                # Drop the 'Ticker' level in the MultiIndex if present
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.droplevel(0)

                # Convert data index to date-only strings
                data.index = data.index.strftime('%Y-%m-%d')

                # Filter the data to include only the specified dates in ordered_end_dates
                filtered_data = data[data.index.isin(ordered_end_dates)]

                # Extract the adjusted close price for each date in filtered_data
                for date in filtered_data.index:
                    adj_close = filtered_data.loc[date, "Adj Close"] if "Adj Close" in filtered_data.columns else None

                    # Append the data row
                    data_rows.append({
                        "Ticker": ticker,
                        "Date": date,
                        "Adj Close": adj_close
                    })

        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")

    # Convert the list of rows into a DataFrame
    extended_df = pd.DataFrame(data_rows)

    # Save the final DataFrame to a CSV file
    extended_df.to_csv("final_prices.csv", index=False)

    # Display the first few rows of the final DataFrame
    print(extended_df.head())

    return extended_df

def get_mda_as_txt(company_tickers: list, start_year: int, output_folder="mda_texts"):
    '''
    This function grabs the 10-Q filing object and saves the text from the Management Discussion and Analysis locally
    as a .txt file
    :param company_tickers: list of strings of stock ticker identifiers
    :param start_year: year to begin grabbing filings
    :param output_folder: string folder name to save the text files
    :return: Saves the text files and prints some analytics based on file handling
    '''
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # Keep count of files saved and failed as some filings are not located in correct spot/format
    saved_count = 0
    failed_count = 0

    for ticker in tqdm(company_tickers, desc="Grabbing each ticker's MD&A"):
        try:
            # Initialize the company
            company = Company(ticker)

            # Fetch all 10-Q filings since the starting year
            filings = company.get_filings(form="10-Q").filter(date=f"{start_year}-01-01:")

            # Loop through each filing
            for filing in filings:
                try:
                    # Get the filing object
                    tenq = filing.obj()

                    # Extract Item 2 (Management's Discussion and Analysis)
                    if "Item 2" in tenq.items:
                        tenq_mda = tenq["Item 2"]

                        # Save the MD&A section as a .txt file
                        if tenq_mda:
                            saved_count += 1
                            filename = f"{ticker}_{filing.filing_date}.txt"
                            filepath = os.path.join(output_folder, filename)
                            with open(filepath, "w", encoding="utf-8") as file:
                                file.write(tenq_mda)
                    else:
                        failed_count += 1
                        print(f"Item 2 not found for {ticker} on {filing.filing_date}")
                except Exception as e:
                    print(f"Error processing filing for {ticker} on {filing.filing_date}: {e}")
        except Exception as e:
            print(f"Error fetching filings for {ticker}: {e}")

    print("Cycle Complete")
    print(f"Saved {saved_count} text files")
    print(f"Failed to save {failed_count} MDA extracts")
    print(f"Successfully saved {(1 - (failed_count/saved_count))*100:.2f} percentage of documents")

def main():

    # Keep track of how long the process runs
    start_time = time.time()

    # Set identity to your name and email, not a credential but for record keeping
    set_identity("Mitchell Hornsby hornsby.m@northeastern.edu")

    # Company tickers of the constituents of the DJIA since 2009 including adds/drops
    tickers = ["AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS",
               "GS", "HD", "HON", "IBM", "JNJ", "JPM", "KO", "MCD", "MMM", "MRK",
               "MSFT", "NKE", "PG", "TRV", "UNH", "V", "VZ", "WMT", "SHW", "NVDA",
               "INTC", "DOW", "GE", "T", "HPQ", "BAC", "AA", "XOM", "PFE", "RTX"]

    # Define start year for grabbing filings and prices
    start_year = 2023

    # Get assets and filing dates since beginning 2009
    final_assets, end_dates_list = get_assets(tickers, start_year)

    # Extract the 'end' dates as a set and sort list
    ordered_end_dates = sorted(set(final_assets.index.strftime('%Y-%m-%d')))

    # Get prices from yahoo finance for filing dates
    final_prices = get_prices(ordered_end_dates, tickers)

    # Get 10-Q MD&A text
    get_mda_as_txt(tickers, start_year)

    # Report how long process took end to end
    elapsed_time = time.time() - start_time
    minutes = elapsed_time // 60
    seconds = elapsed_time % 60
    print(f"Elapsed time for module was {minutes:.2f} minutes and {seconds:.2f} seconds")


if __name__ == '__main__':
    main()