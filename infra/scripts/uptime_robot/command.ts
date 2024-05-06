// Generic command utility, not to be run directly
// Use createUptimeRobotMonitorCommand to create a new command

import "dotenv/config";
import { Command } from "commander";

export const api_key = process.env.UPTIME_ROBOT_API_KEY;

const program = new Command();

const bigLine = "=".repeat(40);
const line = "-".repeat(40);

type HandleCreateMonitor<T> = (
  baseUrl: string,
  path: string,
  options: T
) => Promise<{ data: any; url: string }>;

type CommandParams<T> = {
  description: string;
  handleCreateMonitor: HandleCreateMonitor<T>;
};

export type BasicMonitorOptions = {
  timeout: string;
  interval: string;
};

async function createMonitors<T>(
  baseUrl: string,
  paths: string[],
  options: T,
  handleCreateMonitor: HandleCreateMonitor<T>
) {
  const successfulUrls: string[] = [];
  const failed: { url: string; data: any }[] = [];

  await Promise.all(
    paths.map(async (path) => {
      const { data, url } = await handleCreateMonitor(baseUrl, path, options);
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

export async function createUptimeRobotMonitorCommand<T>({
  description,
  handleCreateMonitor,
}: CommandParams<T>) {
  program
    .description(description)
    .argument("base-url", "Base URL for the monitor(s)")
    .argument("<paths...>", "URL path(s) to monitor")
    .option("-i, --interval <interval>", "Interval in seconds", "60")
    .option("-t, --timeout <timeout>", "Timeout in seconds", "30");

  program.parse();

  const baseUrl = program.args[0].replace(/\/$/, "");
  const paths = program.args.slice(1).map((path) => path.replace(/^\//, ""));

  const options = program.opts() as T;

  console.log(`Creating monitors for ${paths.length} URLs`);

  const { successfulUrls, failed } = await createMonitors(
    baseUrl,
    paths,
    options,
    handleCreateMonitor
  );

  summarize(successfulUrls, failed);
}
