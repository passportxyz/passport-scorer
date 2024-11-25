import os
import requests
from requests_aws4auth import AWS4Auth


def main():
    # Get Lambda Function URL from environment variables
    url = os.getenv("LAMBDA_FUNCTION_URL")
    if not url:
        raise ValueError("LAMBDA_FUNCTION_URL not found in environment variables")

    # Get AWS credentials from environment variables
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION")

    if not all([aws_access_key, aws_secret_key, aws_region]):
        raise ValueError(
            "AWS credentials or region not properly set in environment variables"
        )

    # Create AWS4Auth instance for request signing
    auth = AWS4Auth(aws_access_key, aws_secret_key, aws_region, "lambda")

    # Make the GET request to the Lambda Function URL
    response = requests.get(url, auth=auth)

    # Print the response
    print("Response Status Code:", response.status_code)
    print("Response Body:", response.text)


if __name__ == "__main__":
    main()
