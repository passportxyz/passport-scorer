// Generic command utility, not to be run directly
// Use createUptimeRobotMonitorCommand to create a new command

import "dotenv/config";
import axios from "axios";
import { Command } from "commander";

export const api_key = process.env.UPTIME_ROBOT_API_KEY;

const bigLine = "=".repeat(40);
const line = "-".repeat(40);

type GenerateCreateModelRequestBody<T> = (
  url: string,
  path: string,
  options: T
) => any;

type CommandParams<T> = {
  name: string;
  description: string;
  generateCreateModelRequestBody: GenerateCreateModelRequestBody<T>;
};

export type BasicMonitorOptions = {
  timeout: string;
  interval: string;
};

async function createMonitors<T>(
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

async function createMonitor<T>(
  baseUrl: string,
  path: string,
  options: T,
  generateCreateModelRequestBody: GenerateCreateModelRequestBody<T>
) {
  const url = `${baseUrl}/${path}`;
  const body = generateCreateModelRequestBody(url, path, options);

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
}

export async function generateProgram<T>(commands: CommandParams<T>[]) {
  const program = new Command();
  program.description("Utilities for creating Uptime Robot monitors");

  commands.map(({ name, description, generateCreateModelRequestBody }) => {
    program
      .command(name)
      .description(description)
      .argument("base-url", "Base URL for the monitor(s)")
      .argument("<paths...>", "URL path(s) to monitor")
      .option("-i, --interval <interval>", "Interval in seconds", "60")
      .option("-t, --timeout <timeout>", "Timeout in seconds", "30")
      .action(async (rawBaseUrl: string, rawPaths: string[], options) => {
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
      });
  });

  program.parse();
}
