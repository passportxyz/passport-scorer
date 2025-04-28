import axios, { AxiosRequestConfig, CancelTokenSource } from "axios";
import { TestRequestOptions, TestRequestOptionsNoAuth, TestResponse } from "../types";
import http from "http";
import https from "https";

const generateCancelToken = () => {
  const cancelToken = axios.CancelToken.source();
  if (!global.axiosCancelTokens) {
    global.axiosCancelTokens = [];
  }
  global.axiosCancelTokens.push(cancelToken);
  return cancelToken;
};

const clearCancelToken = (cancelToken: CancelTokenSource) => {
  const index = global.axiosCancelTokens?.indexOf(cancelToken);
  if (index !== undefined && index > -1) {
    global.axiosCancelTokens?.splice(index, 1);
  }
};

/**
 * Makes an HTTP request with optional authentication and returns the response
 * @param options Request options including URL, method, headers, payload, and authentication function
 * @dev Note that payload is automatically translated to query parameters for GET requests
 * @returns Promise resolving to the response with request metadata
 * @throws Error if the request fails or authentication fails
 */
export async function testRequest<T>(options: TestRequestOptions): Promise<TestResponse<T>> {
  try {
    // Start with the base options
    let requestOptions: TestRequestOptionsNoAuth = {
      url: options.url,
      method: options.method,
      headers: normalizeHeaders(options.headers),
      payload: options.payload,
    };

    // Apply authStrategy if provided
    if (options.authStrategy) {
      try {
        requestOptions = await options.authStrategy.applyAuth(requestOptions);
      } catch (authError) {
        throw new Error(
          `Authentication failed for ${options.url} (${options.method}): ${
            authError instanceof Error ? authError.message : "Unknown error"
          }`
        );
      }
    }

    const cancelToken = generateCancelToken();

    // Prepare Axios configuration
    const axiosConfig: AxiosRequestConfig = {
      httpAgent: new http.Agent({ keepAlive: false }),
      httpsAgent: new https.Agent({ keepAlive: false }),
      url: requestOptions.url,
      method: requestOptions.method,
      headers: requestOptions.headers,
      // Only include data if it exists and method is not GET
      ...(requestOptions.payload &&
        requestOptions.method !== "GET" && {
          data: requestOptions.payload,
        }),
      // For GET requests, convert payload to query parameters
      ...(requestOptions.payload &&
        requestOptions.method === "GET" && {
          params: requestOptions.payload,
        }),
      timeout: 30000,
      cancelToken: cancelToken.token,
      validateStatus: () => true, // Don't throw on any status code
    };

    // Make the request
    const response = await axios(axiosConfig);

    clearCancelToken(cancelToken);

    // Return custom response object
    return {
      data: response.data,
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
      requestOptions,
    };
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(`Request to ${options.url} (${options.method}) failed: ${error.message}`);
    }
    throw error;
  }
}

/**
 * Normalizes HTTP headers by ensuring consistent casing and handling common variations
 * @param headers Original headers object
 * @returns Normalized headers object
 */
const normalizeHeaders = (headers: Record<string, string> = {}): Record<string, string> => {
  const normalized: Record<string, string> = {};

  Object.entries(headers).forEach(([key, value]) => {
    // Convert header keys to lowercase for consistency
    const normalizedKey = key.toLowerCase();
    normalized[normalizedKey] = value;
  });

  // Ensure content-type is set for requests with payloads
  if (!normalized["content-type"]) {
    normalized["content-type"] = "application/json";
  }

  return normalized;
};
