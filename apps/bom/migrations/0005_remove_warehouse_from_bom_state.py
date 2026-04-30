from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0004_bom_unique_and_item_str"),
        ("warehouse", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="Warehouse"),
            ],
            database_operations=[],
        ),
    ]
