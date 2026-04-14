from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0004_payment'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['branch', '-created_at'], name='orders_branch_created_idx'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['payment_status'], name='orders_payment_status_idx'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['transaction_type'], name='orders_transaction_type_idx'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['status'], name='orders_status_idx'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['branch', 'payment_status'], name='orders_branch_paystatus_idx'),
        ),
    ]
