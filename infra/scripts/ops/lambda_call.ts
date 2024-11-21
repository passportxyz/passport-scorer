import axios from "axios";
import * as aws4 from "aws4";

const main = async () => {
  // Get environment variables
  const url = process.env.LAMBDA_FUNCTION_URL;
  const awsAccessKeyId = process.env.AWS_ACCESS_KEY_ID;
  const awsSecretAccessKey = process.env.AWS_SECRET_ACCESS_KEY;
  const awsRegion = process.env.AWS_REGION;

  if (!url) {
    throw new Error(
      "LAMBDA_FUNCTION_URL is not set in the environment variables."
    );
  }
  if (!awsAccessKeyId || !awsSecretAccessKey || !awsRegion) {
    throw new Error(
      "AWS credentials or region are not set in the environment variables."
    );
  }

  // Parse the Lambda Function URL
  const { host, pathname } = new URL(url);

  // Sign the request using aws4
  const signedRequest = aws4.sign(
    {
      host,
      path: pathname,
      method: "GET",
      headers: {},
    },
    {
      accessKeyId: awsAccessKeyId,
      secretAccessKey: awsSecretAccessKey,
    }
  );

  try {
    // Make the GET request
    const response = await axios({
      method: signedRequest.method,
      url,
      headers: signedRequest.headers,
    });

    console.log("Response Status Code:", response.status);
    console.log("Response Body:", response.data);
  } catch (error: any) {
    console.error("Error making the request:", error.message);
    if (error.response) {
      console.error("Response Status Code:", error.response.status);
      console.error("Response Body:", error.response.data);
    }
  }
};

main().catch((error) => {
  console.error("Script failed:", error.message);
});
