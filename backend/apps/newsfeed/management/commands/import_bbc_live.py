import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.newsfeed.api_client import BBCFeedError, parse_latest_payload
from apps.newsfeed.services import import_latest, persist_snapshot


class Command(BaseCommand):
    help = "Fetch current BBC headlines and summaries, then upsert them into the local database."

    def add_arguments(self, parser):
        parser.add_argument("--language", default="english", help="BBC language code (default: english)")
        parser.add_argument("--snapshot", type=Path, help="Persist a previously captured API JSON snapshot without making a network request")

    def handle(self, *args, **options):
        try:
            if options["snapshot"]:
                payload = json.loads(options["snapshot"].read_text(encoding="utf-8"))
                result = persist_snapshot(parse_latest_payload(payload, options["language"]))
            else:
                result = import_latest(options["language"])
        except (BBCFeedError, OSError, json.JSONDecodeError) as exc:
            raise CommandError(str(exc)) from exc
        result["snapshot_at"] = result["snapshot_at"].isoformat()
        self.stdout.write(json.dumps(result, indent=2))
