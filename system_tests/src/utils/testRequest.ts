import axios, { AxiosRequestConfig } from 'axios';
import { TestRequestOptions, TestRequestOptionsNoAuth, TestResponse } from '../types';

/**
 * Makes an HTTP request with optional authentication and returns the response
 * @param options Request options including URL, method, headers, payload, and authentication function
 * @returns Promise resolving to the response with request metadata
 * @throws Error if the request fails or authentication fails
 */
export async function testRequest<T = any>(options: TestRequestOptions): Promise<TestResponse<T>> {
  try {
    // Start with the base options
    let requestOptions: TestRequestOptionsNoAuth = {
      url: options.url,
      method: options.method,
      headers: normalizeHeaders(options.headers),
      payload: options.payload,
    };

    // Apply authentication if provided
    if (options.authenticate) {
      try {
        requestOptions = await options.authenticate(requestOptions);
      } catch (authError) {
        throw new Error(
          `Authentication failed for ${options.url} (${options.method}): ${
            authError instanceof Error ? authError.message : 'Unknown error'
          }`
        );
      }
    }

    // Prepare Axios configuration
    const axiosConfig: AxiosRequestConfig = {
      url: requestOptions.url,
      method: requestOptions.method,
      headers: requestOptions.headers,
      // Only include data if it exists and method is not GET
      ...(requestOptions.payload &&
        requestOptions.method !== 'GET' && {
          data: requestOptions.payload,
        }),
      // For GET requests, convert payload to query parameters
      ...(requestOptions.payload &&
        requestOptions.method === 'GET' && {
          params: convertToQueryParams(requestOptions.payload),
        }),
      validateStatus: () => true, // Don't throw on any status code
    };

    // Make the request
    const response = await axios(axiosConfig);

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
  if (!normalized['content-type']) {
    normalized['content-type'] = 'application/json';
  }

  return normalized;
};

/**
 * Converts payload for GET requests to query parameters.
 * @param payload Request payload
 * @returns Query parameters object
 */
const convertToQueryParams = (payload: Record<string, any> = {}): Record<string, any> => {
  return Object.entries(payload).reduce(
    (params, [key, value]) => {
      params[key] = value;
      return params;
    },
    {} as Record<string, any>
  );
};
