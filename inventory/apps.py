from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'
    verbose_name = 'Inventory Management'

    def ready(self):
        """
        Initialize inventory system when Django starts.
        """
        # Import signals to register them
        from . import signals