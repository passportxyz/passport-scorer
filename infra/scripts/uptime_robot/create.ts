import "dotenv/config";

import { BasicMonitorOptions, api_key, generateProgram } from "./command";

const commands = [];

commands.push({
  name: "simple_get",
  description: "Create a new monitor for a public GET endpoint",
  generateCreateModelRequestBody: (
    url: string,
    path: string,
    options: BasicMonitorOptions
  ) => {
    const { timeout, interval } = options;

    return {
      api_key,
      format: "json",
      type: "1",
      friendly_name: "Scorer GET /" + path,
      interval,
      timeout,
      url,
    };
  },
});

type ApiKeyMonitorOptions = BasicMonitorOptions & {
  postBody: string;
  scorerApiKey: string;
};

commands.push({
  name: "api_key_auth",
  description: "Create a new monitor for an endpoint with API key auth",
  generateCreateModelRequestBody: (
    url: string,
    path: string,
    options: ApiKeyMonitorOptions
  ) => {
    const { timeout, interval, postBody, scorerApiKey } = options;

    return {
      api_key,
      format: "json",
      type: "1",
      friendly_name: "Scorer GET /" + path,
      interval,
      timeout,
      url,
    };
  },
});

generateProgram(commands);
