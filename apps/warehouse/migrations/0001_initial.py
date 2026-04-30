from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("bom", "0004_bom_unique_and_item_str"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Warehouse",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("name", models.CharField(max_length=100)),
                        ("code", models.CharField(max_length=10, unique=True)),
                        ("address", models.TextField(blank=True)),
                        ("is_active", models.BooleanField(default=True)),
                    ],
                    options={
                        "db_table": "bom_warehouse",
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
