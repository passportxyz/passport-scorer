import json
import re
from collections import defaultdict
from http.client import HTTPSConnection
from urllib.parse import urlparse, urlunparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from ninja.openapi.schema import OpenAPISchema

from scorer.api import apis

# Will ignore e.g. anything starting with /admin/
IGNORED_PATH_ROOTS = [
    "admin",
    "social",
    "feature",
]

# Will ignore exact path matches
IGNORED_URLS = [
    "/registry/feature/openapi.json",
    "/registry/feature/docs",
    "/registry/feature/scorer/generic",
    "/feature/scorer/generic",
]


class Command(BaseCommand):
    help = "Removes stamp data and sets score to 0 for users in the provided list"

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            type=str,
            help="Output file, json list of unmonitored paths",
            required=True,
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

        if not settings.UPTIME_ROBOT_API_KEY:
            raise CommandError("UPTIME_ROBOT_API_KEY is not set")

        unmonitored_urls = self.get_unmonitored_urls(kwargs)

        self.stdout.write(f"Unmonitored URLs: {len(unmonitored_urls)}")

        self.create_missing_monitors(unmonitored_urls, kwargs["base_url"])

        updated_unmonitored_urls = self.get_unmonitored_urls(kwargs)

        for url in updated_unmonitored_urls:
            self.stdout.write(
                f"Unmonitored After Update: {url['path']} ({url['method']})"
            )

        with open(kwargs["out"], "w") as out_file:
            json.dump(updated_unmonitored_urls, out_file)

        self.stdout.write("Done")

    def get_unmonitored_urls(self, kwargs):
        all_django_urls = self.get_all_urls_with_methods()
        django_urls = self.filter_urls(all_django_urls)

        self.stdout.write(f"Total URLs: {len(all_django_urls)}")
        self.stdout.write(f"Ignoring url path roots: {IGNORED_PATH_ROOTS}")
        self.stdout.write(f"Ignoring urls: {IGNORED_URLS}")
        self.stdout.write(f"URLs to check: {len(django_urls)}")

        monitored_urls = self.get_uptime_robot_urls(
            base_url=kwargs["base_url"], allow_paused=kwargs["allow_paused"]
        )
        self.stdout.write(f"Allowing paused monitors: {kwargs['allow_paused']}")
        self.stdout.write(f"Uptime Robot URLs: {len(monitored_urls)}")
        self.stdout.write(f"Uptime robot URLs: {json.dumps(monitored_urls, indent=2)}")

        unmonitored_urls = []
        for method, data in all_django_urls.items():
            for path in data["paths"]:
                monitor_url = self.replace_placeholders(path)
                matching_monitored_url = next(
                    (url for url in monitored_urls if monitor_url == url), None
                )

                if matching_monitored_url is None:
                    # If the path is not monitored, add it to unmonitored_urls
                    unmonitored_urls.append(
                        {
                            "path": path,
                            "method": method,
                            "request_bodies": data["request_bodies"],
                        }
                    )
                else:
                    self.stdout.write(
                        f"Matched: {path} ({method}) to {matching_monitored_url}"
                    )
                    # Remove the matched URL from monitored_urls
                    monitored_urls.remove(matching_monitored_url)

        return unmonitored_urls

    def replace_placeholders(self, url_path):
        static_replacements = {
            "address": "0x96db2c6d93a8a12089f7a6eda5464e967308aded",
            "scorer_id": "335",
            "tos_type": "IST",
            "banner_id": "1",
            "notification_id": "1",
            "round_id": "1",
        }

        def replace_match(match):
            placeholder = match.group(1)
            return static_replacements.get(placeholder, "placeholder-if-not-found")

        return re.sub(r"{([^}]+)}", replace_match, url_path)

    def create_missing_monitors(self, unmonitored_urls, base_url):
        http_method_map = {
            "HEAD": 1,
            "GET": 2,
            "POST": 3,
            "PUT": 4,
            "PATCH": 5,
            "DELETE": 6,
            "OPTIONS": 7,
        }
        created_monitors = []

        for url_data in unmonitored_urls:
            if "{" in url_data["path"]:
                url_data["path"] = self.replace_placeholders(url_data["path"])

            full_url = f"{base_url}{url_data['path']}"
            friendly_name = f"[auto] {url_data['method']} {url_data['path']}"

            mapped_http_method = http_method_map.get(url_data["method"].upper(), 2)
            try:
                result = self.create_uptime_robot_monitor(
                    friendly_name=friendly_name,
                    url=full_url,
                    monitor_type=1,
                    http_method=mapped_http_method,
                )
                if result.get("stat") == "ok":
                    created_monitors.append(
                        {
                            "path": url_data["path"],
                            "method": url_data["method"],
                            "monitor_id": result.get("monitor", {}).get("id"),
                        }
                    )
                    self.stdout.write(f"Created monitor for: {friendly_name}")
                else:
                    self.stdout.write(
                        f"Failed to create monitor for: {friendly_name}. Error: {result.get('error')}"
                    )
            except Exception as e:
                self.stdout.write(
                    f"Error creating monitor for: {friendly_name}. Error: {str(e)}"
                )

        self.stdout.write(f"Created {len(created_monitors)} new monitors")

    def get_all_urls_with_methods(self):
        combined_data = {}
        for api in apis:
            openapi = OpenAPISchema(api=api, path_prefix="")
            paths = openapi.get("paths", {})
            namespace = api.urls_namespace
            endpoints = self.aggregate_paths_by_method(paths, namespace)

            for method, data in endpoints.items():
                if method not in combined_data:
                    combined_data[method] = data
                else:
                    combined_data[method]["paths"].extend(data["paths"])
                    combined_data[method]["request_bodies"].extend(
                        data["request_bodies"]
                    )
        return combined_data

    def aggregate_paths_by_method(self, paths, namespace):
        aggregated = defaultdict(lambda: {"paths": [], "request_bodies": []})

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
                            aggregated[method]["request_bodies"].append(schema_ref)
        return dict(aggregated)

    def convert_django_url_to_regex(self, url: str):
        # Have to do sub and then replace because re.sub interprets
        # the replacement string as an invalid group reference

        # Sub integers
        url_regex = re.sub("<int:.+?>", "<int>", url).replace("<int>", "\\d+")
        # Sub strings
        url_regex = re.sub("<str:.+?>", "<str>", url_regex).replace("<str>", "[^/]+")
        # Sub untyped params
        url_regex = re.sub("<[^:]+?>", "<str>", url_regex).replace("<str>", "[^/]+")

        return url_regex + "(\\?|$)"

    def get_uptime_robot_urls(self, base_url: str, allow_paused: bool):
        limit = 50
        offset = 0

        monitors = []
        while True:
            data = self.uptime_robot_monitors_request(limit, offset)

            print(data)
            total = data["pagination"]["total"]
            monitors.extend(data["monitors"])

            if len(monitors) >= total:
                break

            offset += limit

        if base_url.endswith("/"):
            base_url = base_url[:-1]

        def remove_query_params(url):
            parsed = urlparse(url)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

        urls = [
            remove_query_params(monitor["url"])
            for monitor in monitors
            if (allow_paused or monitor["status"] != 0)
        ]

        return [url.replace(base_url, "") for url in urls if url.startswith(base_url)]

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
        self, friendly_name, url, monitor_type, http_method=None
    ):
        conn = HTTPSConnection("api.uptimerobot.com")

        custom_http_statuses = "401:1_200:1_201:1"
        # authenticate is a special case, we accept a 400 error since that is thrown if invalid signature is passed
        if "authenticate" in url:
            custom_http_statuses = "401:1_200:1_201:1_400:1"

        payload = {
            "api_key": settings.UPTIME_ROBOT_API_KEY,
            "format": "json",
            "friendly_name": friendly_name,
            "url": url,
            "type": monitor_type,
            "alert_contacts": "6519234_5_1-6365912_5_1",
            "custom_http_statuses": custom_http_statuses,
        }

        if http_method:
            payload["http_method"] = http_method
        if http_method and http_method > 2:
            # We are not passing valid data to the POST requests but these are required
            payload["post_type"] = 1  # raw data
            payload["post_value"] = json.dumps([{"yo": "yo"}])
            payload["post_content_type"] = 1

        headers = {"content-type": "application/json", "cache-control": "no-cache"}

        conn.request("POST", "/v2/newMonitor", json.dumps(payload), headers)

        res = conn.getresponse()
        data = res.read()

        return json.loads(data.decode("utf-8"))

    def get_all_urls(self, urls_file_path):
        with open(urls_file_path) as urls_file:
            urls_json = json.load(urls_file)

        return [entry["url"] for entry in urls_json]

    def filter_urls(self, urls):
        # Remove urls that are just a path with a trailing slash, we
        # don't use these in our api
        filtered_urls = [url for url in urls if not re.match(r"^[^?]*/$", url)]

        filtered_urls = [
            url
            for url in filtered_urls
            if not any(url.startswith("/" + root + "/") for root in IGNORED_PATH_ROOTS)
        ]

        filtered_urls = [
            url
            for url in filtered_urls
            if not any(url == ignored for ignored in IGNORED_URLS)
        ]
        return filtered_urls
