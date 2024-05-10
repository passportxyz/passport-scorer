// Generic command utility
// Call generateProgram with a list of sub-command definitions

import "dotenv/config";
import axios from "axios";
import { Command, Option } from "commander";

const api_key = process.env.UPTIME_ROBOT_API_KEY!;

const checkEnv = () => {
  if (!api_key) {
    console.log("UPTIME_ROBOT_API_KEY must be set in ENV");
    process.exit(1);
  }
};

export const HTTP_METHOD = {
  GET: "2",
  POST: "3",
  PUT: "4",
  PATCH: "5",
  DELETE: "6",
  OPTIONS: "7",
};

const httpMethodToName = (methodId: string) =>
  Object.entries(HTTP_METHOD).find(([_, id]) => id === methodId)?.[0];

const POST_TYPE = {
  KEY_VALUE_PAIRS: "1",
  RAW_DATA: "2",
};

const bigLine = "=".repeat(40);
const line = "-".repeat(40);

// This type is not exhaustive and should be updated as needed
type CreateModelRequestBody = {
  api_key: string;
  format: string;
  type: string;
  interval: string;
  timeout: string;
  url: string;
  status: string;
  http_method?: string;
  custom_http_headers?: Record<string, string>;
  post_value?: string;
  post_type?: string;
  friendly_name?: string;
};

// This function should return a partial CreateModelRequestBody
// which overrides any defaults specified in the CreateMonitor
// function (see below) and adds any additional fields required
type GenerateCreateModelRequestBody<T> = (
  options: T
) => Partial<CreateModelRequestBody>;

type CommandParams<T> = {
  name: string;
  description: string;
  generateCreateModelRequestBody: GenerateCreateModelRequestBody<T>;
  summary?: string; // Optional shorter description listed in top-level help
  additionalOptions?: Option[];
};

export type BaseMonitorOptions = {
  timeout: string;
  interval: string;
  paused: boolean;
};

async function createMonitors<T extends BaseMonitorOptions>(
  baseUrl: string,
  paths: string[],
  options: T,
  generateCreateModelRequestBody: GenerateCreateModelRequestBody<T>
) {
  const successfulUrls: string[] = [];
  const failed: { url: string; data: any }[] = [];

  await Promise.all(
    paths.map(async (path) => {
      const { data, url } = await createMonitor<T>(
        baseUrl,
        path,
        options,
        generateCreateModelRequestBody
      );
      const { stat } = data;
      if (stat === "ok") {
        successfulUrls.push(url);
      } else {
        failed.push({ url, data });
      }
    })
  );

  return { successfulUrls, failed };
}

async function createMonitor<T extends BaseMonitorOptions>(
  baseUrl: string,
  path: string,
  options: T,
  generateCreateModelRequestBody: GenerateCreateModelRequestBody<T>
) {
  const { interval, timeout, paused } = options;

  const url = `${baseUrl}/${path}`;

  const body: CreateModelRequestBody = {
    api_key,
    interval,
    timeout,
    url,
    format: "json",
    type: "1", // HTTP(s)
    status: paused ? "0" : "1",
    ...generateCreateModelRequestBody(options),
  };

  const http_method = body.http_method || HTTP_METHOD.GET;
  const httpMethodName = httpMethodToName(http_method);

  body.friendly_name =
    body.friendly_name || `[auto] Scorer ${httpMethodName} /${path}`;

  if (http_method !== HTTP_METHOD.GET && !body.post_type) {
    body.post_type = POST_TYPE.RAW_DATA;
  }

  let data: any;
  try {
    const response = await axios.post(
      "https://api.uptimerobot.com/v2/newMonitor",
      body,
      {
        headers: {
          "content-type": "application/x-www-form-urlencoded",
          "cache-control": "no-cache",
        },
      }
    );

    data = response.data;
  } catch (exception) {
    data = { exception };
  }

  return {
    data,
    url,
  };
}

async function summarize(
  successfulUrls: string[],
  failed: { url: string; data: any }[]
) {
  console.log(bigLine);
  console.log(`Successfully created ${successfulUrls.length} monitors:`);
  successfulUrls.map((url) => console.log(url));
  console.log(bigLine);

  console.log(`Failed to create ${failed.length} monitors:`);
  failed.forEach(({ url, data }) => {
    console.log(line);
    console.log("URL:", url);
    console.log("Data:", data);
  });
  console.log(bigLine);
  console.log("Done");
}

export async function generateProgram(commands: CommandParams<any>[]) {
  const program = new Command();
  program.description("Utilities for creating Uptime Robot monitors");

  commands.map(
    ({
      name,
      description,
      summary,
      generateCreateModelRequestBody,
      additionalOptions,
    }) => {
      const command = program
        .command(name)
        .description(description)
        .argument("base-url", "Base URL for the monitor(s)")
        .argument("<paths...>", "URL path(s) to monitor (space delimited)")
        .option("-i, --interval <interval>", "Interval in seconds", "60")
        .option("-t, --timeout <timeout>", "Timeout in seconds", "30")
        .option("-p, --paused", "Create the monitor in paused state");

      additionalOptions?.forEach((option) => command.addOption(option));

      summary && command.summary(summary);

      command.action(
        async (rawBaseUrl: string, rawPaths: string[], options) => {
          checkEnv();
          const baseUrl = rawBaseUrl.replace(/\/$/, "");
          const paths = rawPaths.map((path) => path.replace(/^\//, ""));

          console.log(`Creating monitors for ${paths.length} URLs`);

          const { successfulUrls, failed } = await createMonitors(
            baseUrl,
            paths,
            options,
            generateCreateModelRequestBody
          );

          summarize(successfulUrls, failed);
        }
      );
    }
  );

  program.parse();
}
