import requests
from django.core.management.base import BaseCommand
from django.conf import settings

class BaseCronJobCmd(BaseCommand):
    def handle_success(self):
        """
        Make a post request to UptimeRobot Heartbeat Url
        """
        if settings.UPTIME_ROBOT_HEARTBEAT_URL: 
            # {"status":"ok","msg":"Heartbeat request received and processed successfully."}%   
            response = requests.get(settings.UPTIME_ROBOT_HEARTBEAT_URL)
            try: 
                data = response.json()
                if data.get("status", "not_ok") != "ok": 
                    self.stderr.write(f"Error HeartBeat Process. UptimeRobot response: {response}");
            except Exception as e: 
                self.stderr.write(f"Error processing the uptimerobot response: {e}. Original response: {response}")
        else: 
            pass

    def handle(self, *args, **options):
        try:
            self.handle_cron_job(*args, **options)
            self.handle_success()
        except Exception as e:
            # Handle any exceptions that occur during the command execution
            self.stderr.write(f"An error occurred: {e}")

    def handle_cron_job(self, *args, **options):
        # This method will be overridden by child classes
        raise NotImplementedError("handle_cron_job() method must be implemented by child classes")
