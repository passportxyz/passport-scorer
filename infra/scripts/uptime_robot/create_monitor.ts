import "dotenv/config";

import { BaseMonitorOptions, generateProgram, HTTP_METHOD } from "./command";
import { Option } from "commander";

const commands = [];

commands.push({
  name: "simple_get",
  description: "Create a new monitor for a public GET endpoint",
  generateCreateModelRequestBody: (_options: BaseMonitorOptions) => {
    return {};
  },
});

type ApiKeyMonitorOptions = BaseMonitorOptions & {
  postBody?: string;
  scorerApiKey: string;
};

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
    new Option(
      "-d, --data <string>",
      "JSON string data (body) for POST request"
    ),
  ],
  generateCreateModelRequestBody: (options: ApiKeyMonitorOptions) => {
    const { postBody, scorerApiKey } = options;

    const http_method = HTTP_METHOD[postBody !== undefined ? "POST" : "GET"];

    return {
      http_method,
      custom_http_headers: {
        "X-API-KEY": scorerApiKey,
      },
      post_value: postBody,
    };
  },
});

generateProgram(commands);
