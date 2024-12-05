import type { AxiosResponse } from 'axios';
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';

export interface TestRequestOptionsNoAuth {
  url: string;
  method: HttpMethod;
  headers?: Record<string, string>;
  // Converted to query parameters for GET requests
  payload?: Record<string, any>;
}

export type Authenticate = (options: TestRequestOptionsNoAuth) => Promise<TestRequestOptionsNoAuth>;

export interface TestRequestOptions extends TestRequestOptionsNoAuth {
  authenticate?: Authenticate;
}

export interface TestResponse<T = any> extends Omit<AxiosResponse<T>, 'config'> {
  requestOptions: TestRequestOptionsNoAuth;
}
