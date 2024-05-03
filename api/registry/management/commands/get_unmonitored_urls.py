from django.core.management.base import BaseCommand
from django.conf import settings
from http.client import HTTPSConnection
from django.urls import get_resolver, URLPattern
from itertools import chain

import json
import re

# Will ignore e.g. anything starting with /admin/
IGNORED_PATH_ROOTS = [
    "admin",
    "social",
]

# Will ignore exact path matches
IGNORED_URLS = [
    "",
]


def flatten_list(l):
    return list(chain.from_iterable(l))


class Command(BaseCommand):
    help = "Removes stamp data and sets score to 0 for users in the provided list"

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            type=str,
            help="Output file, json list of unmonitored URLs",
            required=True,
        )
        parser.add_argument(
            "--base-url",
            type=str,
            help="Base URL for the site (to prepend to django URLs)",
            required=True,
        )

    def show_urls(self, url_resolver):
        if isinstance(url_resolver, URLPattern):
            return [url_resolver]
        else:
            return flatten_list(
                [self.show_urls(resolver) for resolver in url_resolver.url_patterns]
            )

    def handle(self, *args, **kwargs):
        self.stdout.write("Running ...")
        self.stdout.write(f"args     : {args}")
        self.stdout.write(f"kwargs   : {kwargs}")

        if not settings.UPTIME_ROBOT_READONLY_API_KEY:
            self.stdout.write("UPTIME_ROBOT_READONLY_API_KEY is not set")
            return

        if not kwargs["base_url"].endswith("/"):
            kwargs["base_url"] += "/"

        resolver = get_resolver()
        all_django_url_patterns = self.show_urls(resolver)
        django_url_patterns = self.filter_url_patterns(all_django_url_patterns)

        self.stdout.write(
            f"URLs: {json.dumps([[i, p] for i, p in enumerate([p.pattern._route for p in django_url_patterns])], indent=2)}"
        )

        import pdb

        pdb.set_trace()

        self.stdout.write(f"Total URLs: {len(all_django_url_patterns)}")
        self.stdout.write(f"URLs to check: {len(django_url_patterns)}")

        monitored_urls = self.get_uptime_robot_urls(kwargs["base_url"])
        self.stdout.write(f"Uptime Robot URLs: {len(monitored_urls)}")

        self.stdout.write(f"Uptime robot URLs: {json.dumps(monitored_urls, indent=2)}")

        unmonitored_urls = []
        for url_pattern in django_url_patterns:
            url_regex = url_pattern.pattern.regex

            # Weird one-liner but it works. Basically the inner () is a generator
            # and if anything matches the regex, it will result in a generator that
            # will yield (return to next()) a value, the index of the matching url.
            # Otherwise next() will return the default value of None
            matching_monitored_url_index = next(
                (i for i, url in enumerate(monitored_urls) if re.match(url_regex, url)),
                None,
            )

            if matching_monitored_url_index is None:
                unmonitored_urls.append(django_url)
            else:
                self.stdout.write(
                    f"Matched: {django_url} to {monitored_urls[matching_monitored_url_index]}"
                )
                # remove matching monitored url so it doesn't get matched again
                monitored_urls.pop(matching_monitored_url_index)

        self.stdout.write(f"Unmonitored URLs: {len(unmonitored_urls)}")

        with open(kwargs["out"], "w") as out_file:
            json.dump(unmonitored_urls, out_file)

        self.stdout.write("Done")

    def convert_django_url_to_regex(self, url: str):
        # Have to do sub and then replace because re.sub interprets
        # the replacement string as an invalid group reference
        url_regex = re.sub("<int:.*?>", "<int>", url).replace("<int>", "\\d+")
        url_regex = re.sub("<str:.*?>", "<str>", url_regex).replace("<str>", "[^/]+")
        return url_regex + "$"

    def get_uptime_robot_urls(self, base_url):
        limit = 50
        offset = 0

        urls = []
        while True:
            data = self.uptime_robot_monitors_request(limit, offset)

            total = data["pagination"]["total"]
            urls.extend([monitor["url"] for monitor in data["monitors"]])

            if len(urls) >= total:
                break

            offset += limit

        return [url.replace(base_url, "") for url in urls if url.startswith(base_url)]

    def uptime_robot_monitors_request(self, limit, offset):
        conn = HTTPSConnection("api.uptimerobot.com")

        payload = f"api_key={settings.UPTIME_ROBOT_READONLY_API_KEY}&format=json&limit={limit}&offset={offset}"

        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "cache-control": "no-cache",
        }

        conn.request("POST", "/v2/getMonitors", payload, headers)

        res = conn.getresponse()
        data = res.read()

        return json.loads(data.decode("utf-8"))

    def get_all_urls(self, urls_file_path):
        with open(urls_file_path) as urls_file:
            urls_json = json.load(urls_file)

        return [entry["url"] for entry in urls_json]

    def filter_url_patterns(self, url_patterns):
        filtered_url_patterns = [
            url_pattern
            for url_pattern in url_patterns
            if hasattr(url_pattern.pattern, "_route")
        ]
        filtered_url_patterns = [
            url_pattern
            for url_pattern in filtered_url_patterns
            if not any(
                url_pattern.pattern._route.startswith(root + "/")
                for root in IGNORED_PATH_ROOTS
            )
        ]
        filtered_url_patterns = [
            url_pattern
            for url_pattern in filtered_url_patterns
            if not any(
                url_pattern.pattern._route == ignored for ignored in IGNORED_URLS
            )
        ]
        return filtered_url_patterns
