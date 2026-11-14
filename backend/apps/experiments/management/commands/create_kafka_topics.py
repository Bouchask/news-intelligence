from django.core.management.base import BaseCommand, CommandError

from streaming.kafka_client import TOPICS, create_topics


class Command(BaseCommand):
    help = "Create the News Intelligence Kafka topics."

    def handle(self, *args, **options):
        try:
            created = create_topics()
        except Exception as exc:
            raise CommandError(f"Kafka topic creation failed: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"Topics ready ({len(TOPICS)} configured; {len(created)} created): {', '.join(TOPICS)}"))
