from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("Performance", "0004_bde_performance")]

    operations = [
        migrations.CreateModel(
            name="TVPoster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=160)),
                ("subtitle", models.CharField(blank=True, max_length=255)),
                ("image", models.ImageField(blank=True, null=True, upload_to="tv_posters/%Y/%m/")),
                ("seconds", models.PositiveSmallIntegerField(default=10)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["sort_order", "-created_at"]},
        ),
    ]
