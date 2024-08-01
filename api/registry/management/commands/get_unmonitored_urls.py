import json
from collections import defaultdict
from http.client import HTTPSConnection

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from ninja.openapi.schema import OpenAPISchema

from scorer.api import apis

from .get_unmonitored_urls_config import get_config

http_method_map = {
    "HEAD": 1,
    "GET": 2,
    "POST": 3,
    "PUT": 4,
    "PATCH": 5,
    "DELETE": 6,
    "OPTIONS": 7,
}


class Command(BaseCommand):
    help = "Removes stamp data and sets score to 0 for users in the provided list"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            help="Will not delete or create any monitors, but will fail if URL config is missing",
            action="store_true",
        )
        parser.add_argument(
            "--base-url",
            type=str,
            help="Base URL for the site (uptime robot URLs will be filtered using this)",
            required=True,
        )
        parser.add_argument(
            "--allow-paused",
            type=bool,
            help="Allow paused monitors to be considered monitored (default: False)",
            default=False,
        )

    def handle(self, *args, **kwargs):
        self.stdout.write("Running ...")
        self.stdout.write(f"args     : {args}")
        self.stdout.write(f"kwargs   : {kwargs}")
        if kwargs["dry_run"]:
            self.stdout.write("\n\nThis is a dry run\n\n")

        if not settings.UPTIME_ROBOT_API_KEY:
            raise CommandError("UPTIME_ROBOT_API_KEY is not set")

        monitors = self.get_uptime_robot_urls(kwargs["base_url"], True)
        auto_monitors = monitors["auto_monitors"]
        auto_check_monitors = [
            m["friendly_name"] for m in monitors["auto_check_monitors"]
        ]

        if not kwargs["dry_run"]:
            self.delete_monitors(auto_monitors)

        create_monitor_status = self.get_unmonitored_urls(kwargs, auto_check_monitors)

        self.stdout.write(
            f"Monitors created succesfully: {create_monitor_status['num_successes']}"
        )
        self.stdout.write(
            f"                    failures: {create_monitor_status['num_failures']}"
        )
        self.stdout.write(
            f"                   misconfig: {create_monitor_status['num_missing_config']}"
        )
        self.stdout.write(
            f"          skipped namespaces: {create_monitor_status['num_skipped_namespaces']}"
        )
        self.stdout.write(
            f"           skipped endpoints: {create_monitor_status['num_skipped_endpoints']}"
        )

        if create_monitor_status["num_failures"] > 0:
            raise CommandError("Failed to create required monitor")

    def get_unmonitored_urls(self, kwargs, auto_check_monitors):
        num_failures = 0
        num_successes = 0
        num_missing_config = 0
        num_skipped_namespaces = 0
        num_skipped_endpoints = 0
        config = get_config(kwargs["base_url"])
        for api in apis:
            openapi = OpenAPISchema(api=api, path_prefix="")
            paths = openapi.get("paths", {})

            namespace = api.urls_namespace
            endpoints = self.aggregate_paths_by_method(paths, namespace, openapi)

            namespace_config = config[namespace]["urls"]
            if config[namespace].get("skip"):
                self.stdout.write(f"Skipping monitoring for namespace: {namespace}")
                num_skipped_namespaces += 1
            else:
                for http_method, paths in endpoints.items():
                    for path in paths["paths"]:
                        http_endpoint = (http_method, path)
                        endpoint_config = namespace_config.get(http_endpoint)
                        mapped_http_method = http_method_map.get(http_method, 2)

                        if endpoint_config is not None:
                            friendly_name = f"[auto] {http_method} {path}"
                            if endpoint_config.get("skip"):
                                num_skipped_endpoints += 1
                                self.stdout.write(
                                    f"\nSkipping monitoring for: {http_endpoint}\n"
                                )
                                # Skipped endpoints needs to have a manual monitor from the auto_check list
                                friendly_auto_check_name = (
                                    f"[auto-check] {http_method} {path}"
                                )
                                if friendly_auto_check_name not in auto_check_monitors:
                                    self.stderr.write(
                                        f"!!! Missing monitor '{friendly_auto_check_name}': \n\t\t{http_endpoint}"
                                    )
                                    num_failures += 1

                            elif not kwargs["dry_run"]:
                                monitor_status = self.create_uptime_robot_monitor(
                                    friendly_name=friendly_name,
                                    url=endpoint_config["url"],
                                    monitor_type=1,
                                    http_method=mapped_http_method,
                                    custom_http_headers=endpoint_config.get(
                                        "http_headers"
                                    ),
                                    body=endpoint_config.get("payload"),
                                    success_http_statues=endpoint_config.get(
                                        "success_http_statues"
                                    ),
                                )
                                if monitor_status["stat"] != "ok":
                                    self.stderr.write(
                                        f"!!! Failed creation of monitor: {http_endpoint}:\n{monitor_status}"
                                    )
                                    num_failures += 1
                                else:
                                    num_successes += 1
                        else:
                            self.stderr.write(
                                f"!!! Missing config for: {http_endpoint}"
                            )
                            num_failures += 1
                            num_missing_config += 1
        return {
            "num_failures": num_failures,
            "num_successes": num_successes,
            "num_missing_config": num_missing_config,
            "num_skipped_namespaces": num_skipped_namespaces,
            "num_skipped_endpoints": num_skipped_endpoints,
        }

    def get_all_urls_with_methods(self):
        combined_data = {}
        for api in apis:
            openapi = OpenAPISchema(api=api, path_prefix="")
            paths = openapi.get("paths", {})

            namespace = api.urls_namespace
            endpoints = self.aggregate_paths_by_method(paths, namespace, openapi)

            for method, data in endpoints.items():
                if method not in combined_data:
                    combined_data[method] = data
                else:
                    combined_data[method]["paths"].extend(data["paths"])
                    combined_data[method]["request_bodies"].extend(
                        data["request_bodies"]
                    )
        return combined_data

    def aggregate_paths_by_method(self, paths, namespace, openapi):
        aggregated = defaultdict(lambda: {"paths": [], "request_bodies": []})

        components = openapi.get_components()

        for path, methods in paths.items():
            for method, details in methods.items():
                method = method.upper()
                # Split the path into components
                path_components = path.strip("/").split("/")

                # Check if the namespace is already in the path
                if namespace:
                    namespace_parts = namespace.split("_")
                    if all(part in path_components for part in namespace_parts):
                        prefixed_path = path
                    else:
                        prefixed_path = f"/{namespace}{path}"
                else:
                    prefixed_path = path
                aggregated[method]["paths"].append(prefixed_path)

                if "requestBody" in details:
                    request_body = details["requestBody"]
                    if "content" in request_body:
                        content_type = next(iter(request_body["content"]))
                        schema_ref = request_body["content"][content_type][
                            "schema"
                        ].get("$ref")
                        if schema_ref:
                            schema = schema_ref.rsplit("/", 1)[-1]
                            request_param_schema = components["schemas"].get(schema)
                            aggregated[method]["request_bodies"].append(
                                request_param_schema
                            )

        return dict(aggregated)

    def get_uptime_robot_urls(self, base_url: str, allow_paused: bool):
        limit = 50
        offset = 0

        monitors = []
        while True:
            data = self.uptime_robot_monitors_request(limit, offset)

            total = data["pagination"]["total"]
            monitors.extend(data["monitors"])

            if len(monitors) >= total:
                break

            offset += limit

        auto_monitors = [m for m in monitors if m["friendly_name"].startswith("[auto]")]

        # The auto-check monitors are the ones that are created manually
        # but we will still check if they exist
        auto_check_monitors = [
            m for m in monitors if m["friendly_name"].startswith("[auto-check]")
        ]
        for m in auto_monitors:
            print(m["id"], m["friendly_name"])

        return {
            "auto_monitors": auto_monitors,
            "auto_check_monitors": auto_check_monitors,
        }

    def delete_monitors(self, monitors: list[dict]):
        conn = HTTPSConnection("api.uptimerobot.com")

        for m in monitors:
            self.stdout.write(f"Deleting monitor {m['id']} - {m['friendly_name']}")
            payload = (
                f"api_key={settings.UPTIME_ROBOT_API_KEY}&format=json&id={m['id']}"
            )

            headers = {
                "content-type": "application/x-www-form-urlencoded",
                "cache-control": "no-cache",
            }

            conn.request("POST", "/v2/deleteMonitor", payload, headers)

            res = conn.getresponse()
            data = res.read()
            data = json.loads(data.decode("utf-8"))

            if data["stat"] != "ok":
                self.stderr.write(
                    f"Error deleting monitor {m['id']} - {m['friendly_name']}"
                )

    def uptime_robot_monitors_request(self, limit, offset):
        conn = HTTPSConnection("api.uptimerobot.com")

        payload = f"api_key={settings.UPTIME_ROBOT_API_KEY}&format=json&limit={limit}&offset={offset}"

        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "cache-control": "no-cache",
        }

        conn.request("POST", "/v2/getMonitors", payload, headers)

        res = conn.getresponse()
        data = res.read()

        return json.loads(data.decode("utf-8"))

    def create_uptime_robot_monitor(
        self,
        friendly_name,
        url,
        monitor_type,
        http_method=None,
        custom_http_headers=None,
        success_http_statues=None,
        body=None,
    ):
        if not success_http_statues:
            success_http_statues = [200]

        conn = HTTPSConnection("api.uptimerobot.com")

        custom_http_statuses = "-".join(
            [f"{status}:1" for status in success_http_statues]
        )

        payload = {
            "api_key": settings.UPTIME_ROBOT_API_KEY,
            "format": "json",
            "friendly_name": friendly_name,
            "url": url,
            "type": monitor_type,
            "alert_contacts": "6519234_5_1-6365912_5_1",
            "custom_http_statuses": custom_http_statuses,
        }

        if custom_http_headers:
            payload["custom_http_headers"] = custom_http_headers

        if http_method:
            payload["http_method"] = http_method

        if body is not None:
            # We are not passing valid data to the POST requests but these are required
            payload["post_type"] = 1  # raw data
            payload["post_value"] = json.dumps(body)
            payload["post_content_type"] = 0

        headers = {"content-type": "application/json", "cache-control": "no-cache"}

        conn.request("POST", "/v2/newMonitor", json.dumps(payload), headers)

        res = conn.getresponse()
        data = res.read()

        self.stdout.write(f"Create monitor: {friendly_name}")

        return json.loads(data.decode("utf-8"))
