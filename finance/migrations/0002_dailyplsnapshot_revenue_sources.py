from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('branches', '0002_branch_manager_email'),
        ('finance', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DailyPLSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('total_revenue', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('total_expenses', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('cogs', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('net_profit', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='daily_pl_snapshots', to='branches.branch')),
            ],
            options={
                'verbose_name': 'Daily P&L snapshot',
                'ordering': ['-date'],
                'unique_together': {('branch', 'date')},
            },
        ),
        migrations.AlterField(
            model_name='revenue',
            name='source',
            field=models.CharField(
                choices=[
                    ('sales', 'Product Sales'),
                    ('sale', 'Sale'),
                    ('customization', 'Customization Fees'),
                    ('refund', 'Refund received'),
                    ('investment', 'Investment'),
                    ('grant', 'Grant'),
                    ('other', 'Other'),
                ],
                default='sales',
                max_length=20,
            ),
        ),
    ]
