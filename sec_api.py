import json
import requests
import os

def download_10q_reports(ticker):
    # Load company tickers from the JSON file
    with open('company_tickers.json') as f:
        company_data = json.load(f)

    # Find the company by ticker
    company_info = next((info for info in company_data.values() if info['ticker'] == ticker), None)

    if not company_info:
        print(f"No data found for ticker: {ticker}")
        return

    cik = company_info['cik_str']
    base_url = "https://data.sec.gov/api/xbrl/"
    headers = {
        'User-Agent': 'Your Name AdminContact@yourdomain.com',  # Change this line
        'Accept-Encoding': 'gzip, deflate'
    }

    # Fetch 10-Q filings
    filings_url = f"https://data.sec.gov/submissions/CIK{str(cik).zfill(10)}.json"
    response = requests.get(filings_url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to fetch filings for CIK {cik}: {response.text}")
        return

    filings_data = response.json()
    
    # Extract recent filings
    recent_filings = filings_data['filings']['recent']
    
    # Create a list of filings with relevant data
    reports = []
    for i in range(len(recent_filings['form'])):
        if recent_filings['form'][i] == '10-Q':
            print(recent_filings.keys())
            report = {
                'form': recent_filings['form'][i],
                'filingDate': recent_filings['filingDate'][i],
                'accessionNumber': recent_filings['accessionNumber'][i],
                'fileName': recent_filings['primaryDocument'][i]
            }
            reports.append(report)

    # Download up to 10 reports
    for report in reports[:10]:
        filing_date = report['filingDate']
        accession_number = report['accessionNumber']
        report_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number.replace('-', '')}/{report['fileName']}"

        # Define the download path
        download_path = os.path.join(os.getcwd(), f"{ticker}_10Q_{filing_date}.txt")

        print(f"Downloading: {report_url} to {download_path}")
        report_response = requests.get(report_url, headers=headers)

        if report_response.status_code == 200:
            with open(download_path, 'wb') as f:
                f.write(report_response.content)
            print(f"Downloaded: {download_path}")
        else:
            print(f"Failed to download report: {report_response.text}")

if __name__ == "__main__":
    ticker_input = input("Enter the ticker symbol (e.g., AAPL): ").strip()
    download_10q_reports(ticker_input)
