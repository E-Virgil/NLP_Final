from edgar import Company, set_identity
import pandas as pd
from tqdm import tqdm
import yfinance as yf
import time
import os

#  https://pypi.org/project/edgartools/3.0.1/

def adjust_to_next_business_day(date_str):
    '''
    Adjust a given date string to the next business day if it falls on a weekend or non-trading day.
    :param date_str: A date string in the format 'YYYY-MM-DD'
    :return: A string representing the next business day
    '''
    # Convert the string to a pandas Timestamp
    date = pd.Timestamp(date_str)

    # If it's already a business day, return as is
    if date.weekday() < 5:  # Monday to Friday are 0-4
        return date.strftime('%Y-%m-%d')

    # If it's a weekend, adjust to the next business day
    next_business_day = pd.bdate_range(start=date, periods=1)[0]
    return next_business_day.strftime('%Y-%m-%d')

def get_assets(tickers: list, start_year: int):
    '''
    This function takes a list of ticker symbols and retrieves the asset values for the given timeframe from SEC EDGAR
    database using the edgartools module.  It saves as a csv file locally and returns the data frame and a dictionary
    of related filing dates.
    :param tickers: list of strings of stock ticker identifiers
    :param start_year: year to begin grabbing filings
    :return: data frame of assets with dates organized including tickers as well as a dictionary of related filing dates
    for each ticker
    '''
    # Initialize an empty dictionary to store dates by ticker
    ticker_filed_dates = {}

    # Initialize an empty list to store DataFrames
    all_data = []

    # Loop through each ticker
    for ticker in tqdm(tickers, desc="Grabbing each ticker's assets..."):
        try:
            # Initialize the Company instance
            company = Company(ticker)

            # Retrieve all 10-Q and 10-K filings since start_year
            filings_q = company.get_filings(form="10-Q").filter(date=f"{start_year}-01-01:")
            filings_k = company.get_filings(form="10-K").filter(date=f"{start_year}-01-01:")

            # Convert filings to a DataFrame and filter for 'Assets' fact
            df_q = company.get_facts().to_pandas()
            df_k = company.get_facts().to_pandas()
            df_q = df_q[df_q['filed'] >= f"{start_year}-01-01"].copy()
            df_k = df_k[df_k['filed'] >= f"{start_year}-01-01"].copy()
            df_q = df_q.query("fact == 'Assets' and form == '10-Q'").copy()
            df_k = df_k.query("fact == 'Assets' and form == '10-K'").copy()

            # Combine 10-Q and 10-K DataFrames
            combined_df = pd.concat([df_q, df_k])

            # Ensure 'filed' and 'end' columns are datetime
            combined_df['filed'] = pd.to_datetime(combined_df['filed']).copy()
            combined_df['end'] = pd.to_datetime(combined_df['end']).copy()

            # Sort by end date and then by filed date
            combined_df = combined_df.sort_values(by=['end', 'filed']).copy()

            # Deduplicate to keep only the first instance per end date
            filtered_df = combined_df.drop_duplicates(subset='end', keep='first').copy()

            # Add the ticker symbol to the DataFrame
            filtered_df.loc[:,"Ticker"] = ticker

            # Append the filtered data to the all_data list
            all_data.append(filtered_df)

            # Store unique filed dates for this ticker
            ticker_filed_dates[ticker] = sorted(set(filtered_df['filed'].dt.strftime('%Y-%m-%d')))

        except Exception as e:
            print(f"An error occurred for ticker {ticker}: {e}")

    # Combine all individual DataFrames into one
    final_df = pd.concat(all_data)

    # Save the final DataFrame to a CSV file
    final_df.to_csv("assets_data.csv")

    return final_df, ticker_filed_dates

def get_prices(ticker_filed_dates: dict):
    '''
    This function gets the prices from yahoo finance using yfinance module for comparative purposes to the assets from
    SEC EDGAR database.  It saves as a csv file locally and returns the data frame.
    :param ticker_filed_dates: dictionary of related stock tickers and 10-Q filing dates
    :return: data frame of prices and period returns with dates organized including tickers
    '''

    # Initialize an empty list to store DataFrame rows
    data_rows = []

    # Loop through each ticker and its associated filed dates
    for ticker, dates in tqdm(ticker_filed_dates.items(), desc="Grabbing each ticker's prices..."):
        try:
            # Adjust all dates to the next business day
            adjusted_dates = [adjust_to_next_business_day(date) for date in dates]

            # Determine the min and max dates for this ticker
            min_date = min(adjusted_dates)
            max_date = (pd.Timestamp(max(adjusted_dates)) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')  # Extend by 1 day

            # Fetch data for the date range of this ticker
            data = yf.download(ticker, start=min_date, end=max_date, group_by="ticker", progress=False)

            # Check if data is not empty
            if not data.empty:
                # Drop the 'Ticker' level in the MultiIndex if present
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.droplevel(0)

                # Convert data index to date-only strings
                data.index = data.index.strftime('%Y-%m-%d')

                # Filter the data to include only the adjusted filed dates for this ticker
                filtered_data = data[data.index.isin(adjusted_dates)]

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

    # Calculate interperiod returns grouped by ticker
    extended_df['Interperiod Return Pct'] = (
        extended_df.groupby('Ticker')['Adj Close']
        .pct_change()  # Compute percentage change
    )

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
    start_year = 2016

    # Get assets and filing dates since beginning start_year
    final_assets, ticker_dates = get_assets(tickers, start_year)

    # Get prices from yahoo finance for filing dates
    final_prices = get_prices(ticker_dates)

    # Get 10-Q MD&A text
    get_mda_as_txt(tickers, start_year)

    # Report how long process took end to end
    elapsed_time = time.time() - start_time
    minutes = elapsed_time // 60
    seconds = elapsed_time % 60
    print(f"Elapsed time for module was {minutes:.2f} minutes and {seconds:.2f} seconds")


if __name__ == '__main__':
    main()