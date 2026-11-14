from django.core.management.base import BaseCommand, CommandError

from streaming.consumers import run_consumer


class Command(BaseCommand):
    help = "Run a Kafka pipeline consumer: raw, classify, or results."

    def add_arguments(self, parser):
        parser.add_argument("mode", choices=("raw", "classify", "results"))

    def handle(self, *args, **options):
        try:
            run_consumer(options["mode"])
        except Exception as exc:
            raise CommandError(f"Kafka consumer stopped: {exc}") from exc
