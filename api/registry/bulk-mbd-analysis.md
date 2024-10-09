# CSV Upload and Processing in Django Admin

This document outlines the process for uploading a CSV file to the Django admin interface, checking the result status, and downloading the processed file.

## Prerequisites

- Access to the Django admin interface at api.scorer.gitcoin.co
- A CSV file containing the data to be processed

## Steps

### 1. Login to Django Admin

1. Open your web browser and navigate to [api.scorer.gitcoin.co/admin](https://api.scorer.gitcoin.co/admin)
2. Log in with your google account

### 2. Navigate to Batch Model Scoring Request

1. Once logged in, navigate to `/registry/batchmodelscoringrequest`

### 3. Upload CSV File

1. Click on the "Upload Address" button
2. In the form that appears:
   - Select the models you want to use for scoring
   - Upload your CSV file
3. Click "Save" to submit the form

expected csv format:

```
Address
0x1234
0x5678
```

### 4. Check Result Status

After saving, you will be redirected to a page showing:

- The progress of the processing
- A link to the uploaded file in S3
- A link to the results file
