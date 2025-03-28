import type { AxiosResponse } from "axios";
export type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";

export interface AuthStrategy {
  name: string;
  applyAuth(options: TestRequestOptionsNoAuth): Promise<TestRequestOptionsNoAuth>;
}

export interface TestRequestOptionsNoAuth {
  url: string;
  method: HttpMethod;
  headers?: Record<string, string>;
  // Converted to query parameters for GET requests
  payload?: Record<string, any>;
}

export interface TestRequestOptions extends TestRequestOptionsNoAuth {
  authStrategy?: AuthStrategy;
}

export interface TestResponse<T = any> extends Omit<AxiosResponse<T>, "config"> {
  requestOptions: TestRequestOptionsNoAuth;
}
