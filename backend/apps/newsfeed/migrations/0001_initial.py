from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="LiveNewsItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("article_url", models.URLField(max_length=600, unique=True)),
                ("title", models.CharField(max_length=500)),
                ("summary", models.TextField(blank=True)),
                ("image_url", models.URLField(blank=True, max_length=1000)),
                ("sections", models.JSONField(default=list)),
                ("language", models.CharField(db_index=True, default="english", max_length=30)),
                ("snapshot_at", models.DateTimeField(db_index=True)),
                ("first_seen_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True, db_index=True)),
            ],
            options={"ordering": ("-last_seen_at", "title")},
        ),
        migrations.AddIndex(
            model_name="livenewsitem",
            index=models.Index(fields=["language", "-last_seen_at"], name="newsfeed_li_languag_ce572f_idx"),
        ),
    ]
