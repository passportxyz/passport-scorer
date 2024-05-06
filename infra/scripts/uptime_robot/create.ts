import "dotenv/config";

import axios from "axios";
import {
  BasicMonitorOptions,
  createUptimeRobotMonitorCommand,
  api_key,
} from "./command";

const createSimpleGETMonitor = async (
  baseUrl: string,
  path: string,
  options: BasicMonitorOptions
) => {
  const { timeout, interval } = options;

  const url = `${baseUrl}/${path}`;

  let data: any;
  try {
    const response = await axios.post(
      "https://api.uptimerobot.com/v2/newMonitor",
      {
        api_key,
        format: "json",
        type: "1",
        friendly_name: "Scorer GET /" + path,
        interval,
        timeout,
        url,
      },
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
};

createUptimeRobotMonitorCommand<BasicMonitorOptions>({
  description: "Create a new monitor for a public GET endpoint",
  handleCreateMonitor: createSimpleGETMonitor,
});
