import datetime
from django.core.management.base import BaseCommand


class BaseCronJobCmd(BaseCommand):
    def log_time(self, message, current_time):
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
        self.stdout.write(f"{message}: {formatted_time}")

    def handle(self, *args, **options):
        try:
            start_time = datetime.datetime.now()
            self.log_time("[TIMING] Start job", start_time)
            self.handle_cron_job(*args, **options)
        except Exception as e:
            # Handle any exceptions that occur during the command execution
            self.stderr.write(f"An error occurred: {e}")
        finally:
            end_time = datetime.datetime.now()
            self.log_time("[TIMING] End job", end_time)
            duration = end_time - start_time
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.stdout.write(
                f"[TIMING] Job duration: {int(hours)} hours, {int(minutes)} minutes, {int(seconds)} seconds"
            )

    def handle_cron_job(self, *args, **options):
        # This method will be overridden by child classes
        raise NotImplementedError(
            "handle_cron_job() method must be implemented by child classes"
        )
