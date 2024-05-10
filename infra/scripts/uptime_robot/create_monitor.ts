import "dotenv/config";

import { BaseMonitorOptions, generateProgram, HTTP_METHOD } from "./command";
import { Option } from "commander";

type NonGetMonitorOptions = BaseMonitorOptions & {
  postBody?: string;
  method?: keyof typeof HTTP_METHOD;
};

type ApiKeyMonitorOptions = NonGetMonitorOptions & {
  scorerApiKey: string;
};

type TokenMonitorOptions = NonGetMonitorOptions & {
  token: string;
};

const commands = [];

commands.push({
  name: "simple_get",
  description: "Create a new monitor for a public GET endpoint",
  generateCreateModelRequestBody: (_options: BaseMonitorOptions) => {
    return {};
  },
});

const NON_GET_OPTIONS = [
  new Option(
    "-d, --data <string>",
    "JSON string data (body), by default turns into POST request"
  ),
  new Option(
    "-m, --method <PATCH|...>",
    "HTTP method (default GET, or POST if -d is provided)"
  ),
];

function getHttpMethod<T extends NonGetMonitorOptions>(options: T) {
  const { postBody, method } = options;
  if (method) {
    return HTTP_METHOD[method];
  } else {
    return postBody ? HTTP_METHOD.POST : HTTP_METHOD.GET;
  }
}

commands.push({
  name: "api_key_auth",
  summary: "Create a new monitor for an endpoint with API key auth",
  description:
    "Create a new monitor for an endpoint with API key auth (defaults to GET request)",
  additionalOptions: [
    new Option(
      "-k, --scorer-api-key <string>",
      "(required) Scorer API key to be passed as X-API-Key"
    ).makeOptionMandatory(),
    ...NON_GET_OPTIONS,
  ],
  generateCreateModelRequestBody: (options: ApiKeyMonitorOptions) => {
    const { postBody, scorerApiKey } = options;

    const http_method = getHttpMethod(options);

    return {
      http_method,
      custom_http_headers: {
        "X-API-KEY": scorerApiKey,
      },
      post_value: postBody,
    };
  },
});

commands.push({
  name: "token_auth",
  summary: "Create a new monitor for an endpoint with JWT token auth",
  description:
    "Create a new monitor for an endpoint with JWT token auth (defaults to GET request)",
  additionalOptions: [
    new Option(
      "-j, --jwt-token <string>",
      "(required) JWT auth token (generate with django command `generate_ceramiccache_access_token`)"
    ).makeOptionMandatory(),
    ...NON_GET_OPTIONS,
  ],
  generateCreateModelRequestBody: (options: TokenMonitorOptions) => {
    const { postBody, token } = options;

    const http_method = getHttpMethod(options);

    return {
      http_method,
      custom_http_headers: {
        AUTHORIZATION: `Bearer ${token}`,
      },
      post_value: postBody,
    };
  },
});

generateProgram(commands);
