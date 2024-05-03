from django.core.management.base import BaseCommand
from django.conf import settings
from http.client import HTTPSConnection

import json
import re

# Will ignore e.g. anything starting with /admin/
IGNORED_PATH_ROOTS = [
    "admin",
    "social",
]

# Will ignore exact path matches
IGNORED_URLS = [
    "/",
]


class Command(BaseCommand):
    help = "Removes stamp data and sets score to 0 for users in the provided list"

    def add_arguments(self, parser):
        parser.add_argument(
            "--urls",
            type=str,
            help="""Local path to a file containing json output of `show_urls` command""",
            required=True,
        )
        parser.add_argument(
            "--out",
            type=str,
            help="Output file, json list of unmonitored URLs",
            # TODO
            # required=True,
            required=False,
        )
        parser.add_argument(
            "--base-url",
            type=str,
            help="Base URL for the site (to prepend to django URLs)",
            required=True,
        )

    def handle(self, *args, **kwargs):
        self.stdout.write("Running ...")
        self.stdout.write(f"args     : {args}")
        self.stdout.write(f"kwargs   : {kwargs}")

        if not settings.UPTIME_ROBOT_READONLY_API_KEY:
            self.stdout.write("UPTIME_ROBOT_READONLY_API_KEY is not set")
            return

        all_django_url_paths = self.get_all_urls(kwargs["urls"])
        filtered_django_url_paths = self.filter_urls(all_django_url_paths)
        django_urls = [kwargs["base_url"] + url for url in filtered_django_url_paths]

        self.stdout.write(f"Total URLs: {len(all_django_url_paths)}")
        self.stdout.write(f"URLs to check: {len(django_urls)}")

        monitored_urls = self.get_uptime_robot_urls()
        self.stdout.write(f"Uptime Robot URLs: {len(monitored_urls)}")

        unmonitored_urls = []
        for django_url in django_urls:
            url_regex = self.convert_django_url_to_regex(django_url)

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

        # output the difference
        self.stdout.write(f"Unmonitored URLs: {len(unmonitored_urls)}")
        self.stdout.write(f"Unmonitored URLs: {unmonitored_urls}")

    def convert_django_url_to_regex(self, url: str):
        # Have to do sub and then replace because re.sub interprets
        # the replacement string as an invalid group reference
        url_regex = re.sub("<int:.*?>", "<int>", url).replace("<int>", "\\d+")
        url_regex = re.sub("<str:.*?>", "<str>", url_regex).replace("<str>", "[^/]+")
        return url_regex + "$"

    def get_uptime_robot_urls(self):
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

        return urls

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

    def filter_urls(self, urls):
        filtered_urls = [
            url
            for url in urls
            if not any(url.startswith("/" + root + "/") for root in IGNORED_PATH_ROOTS)
        ]
        filtered_urls = [
            url
            for url in filtered_urls
            if not any(url == ignored for ignored in IGNORED_URLS)
        ]
        return filtered_urls
