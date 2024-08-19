import json
import sys
from io import StringIO

import pandas as pd
import requests


def fetch_csv_from_url(url):
    """
    Fetch a CSV file from the given URL and return it as a pandas DataFrame.

    Args:
    url (str): The URL of the CSV file to fetch.

    Returns:
    pandas.DataFrame: A DataFrame containing the CSV data.

    Raises:
    requests.RequestException: If there's an error fetching the URL.
    pd.errors.EmptyDataError: If the CSV is empty or improperly formatted.
    """
    try:
        # Fetch the CSV content from the URL
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Create a StringIO object from the content
        csv_content = StringIO(response.text)

        # Read the CSV content into a pandas DataFrame
        df = pd.read_csv(csv_content)
        return df

    except requests.RequestException as e:
        print(f"Error fetching CSV from URL: {e}")
        raise
    except pd.errors.EmptyDataError:
        print("The CSV file is empty or improperly formatted.")
        raise


def check_score_negative_one(result_str):
    try:
        result_dict = json.loads(result_str)
        for model in result_dict.get("models", {}).values():
            if model.get("score") == -1:
                return True
        return False
    except json.JSONDecodeError:
        return False


def process_csv_and_save_errors(urls, output_filename="error_addresses.csv"):
    all_error_dfs = []

    for url in urls:
        try:
            # Fetch the CSV file
            df = fetch_csv_from_url(url)

            # Filter the DataFrame to get addresses with score -1
            error_addresses = df[df["Result"].apply(check_score_negative_one)][
                "Address"
            ]

            # Create a new DataFrame with the error addresses
            error_df = pd.DataFrame(error_addresses, columns=["Address"])
            all_error_dfs.append(error_df)

            print(f"Processed URL: {url}")
            print(f"Found {len(error_df)} addresses with score -1.")

        except Exception as e:
            print(f"Error processing URL {url}: {str(e)}")

    if all_error_dfs:
        # Combine all error DataFrames
        combined_error_df = pd.concat(all_error_dfs, ignore_index=True)

        # Remove duplicates
        combined_error_df.drop_duplicates(inplace=True)

        # Save the combined error addresses to a new CSV file
        combined_error_df.to_csv(output_filename, index=False)

        print(f"Total unique error addresses: {len(combined_error_df)}")
        print(f"Saved to {output_filename}")
    else:
        print("No valid data was processed. No output file created.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        urls = sys.argv[1:]
    else:
        urls = [
            "https://bulk-score-requests-staging.s3.amazonaws.com/model-score-results/2024-08-19_21-49-25.csv?AWSAccessKeyId=AKIAXQB3OF2K6SL73W4R&Signature=FgkjxN4FAVrzaR7wChhaErJjmSg%3D&Expires=1724107900"
        ]
        print("No URLs provided. Using default URL.")

    process_csv_and_save_errors(urls, "combined_error_addresses-fourth-run.csv")
