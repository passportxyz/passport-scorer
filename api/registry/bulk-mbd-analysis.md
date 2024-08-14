# CSV Upload and Processing in Django Admin

This document outlines the process for uploading a CSV file to the Django admin interface, checking the result status, and downloading the processed file.

## Prerequisites

- Access to the Django admin interface at api.scorer.gitcoin.co
- A CSV file containing the data to be processed
- API key (found in 1Password)

## Steps

### 1. Login to Django Admin

1. Open your web browser and navigate to [api.scorer.gitcoin.co](https://api.scorer.gitcoin.co)
2. Log in with your google account

### 2. Navigate to Batch Model Scoring Request

1. Once logged in, navigate to `/registry/batchmodelscoringrequest`

### 3. Upload CSV File

1. Click on the "Upload Address" button
2. In the form that appears:
   - Select the models you want to use for scoring
   - Upload your CSV file
3. Click "Save" to submit the form

### 4. Check Result Status

After saving, you will be redirected to a page showing:
- The progress of the processing
- A link to the uploaded file in S3
- A link to the results file

### 5. Query Recent Uploads (Optional)

You can also check the status of recent uploads using an API endpoint:

1. Open a terminal
2. Run the following curl command:

   ```bash
   curl -X 'GET' \
   'http://localhost:8002/internal/analysis/batch?limit=10' \
   -H 'accept: application/json' \
   -H 'AUTHORIZATION: abc'
   ```

   Note: Replace `abc` with your actual API key from 1Password

3. The response will include:
   - Links to the uploaded and results files
   - The current status of the processing

## Downloading Results

Once the processing is complete, you can download the results file using the link provided in step 4 or in the API response from step 5.

## Troubleshooting

If you encounter any issues during this process, please contact the engineering team for assistance.
