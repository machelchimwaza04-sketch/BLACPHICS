from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError


class Branch(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True, null=True, blank=True, help_text='Short unique branch code used for sequences')
    city = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.CharField(max_length=20)
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    manager_email = models.EmailField(blank=True, help_text='Email for low stock alerts')

    def __str__(self):
        return f"{self.name} - {self.city}"

    class Meta:
        verbose_name_plural = "Branches"


class User(AbstractUser):
    """
    Custom User model with role-based access control and branch association.
    """
    ROLE_CHOICES = [
        ('admin', 'System Administrator'),
        ('branch_manager', 'Branch Manager'),
        ('cashier', 'Cashier'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='cashier',
        help_text='User role determines permissions'
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        null=True,  # Allow null for admin users
        blank=True,
        related_name='users',
        help_text='Branch assignment (null for system admins)'
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Ensure unique usernames across the system
        unique_together = ['username']

    def clean(self):
        """Validate user data based on role."""
        super().clean()

        # System admins don't need a branch
        if self.role == 'admin':
            if self.branch is not None:
                raise ValidationError("System administrators cannot be assigned to a specific branch.")
        else:
            # Non-admin users must have a branch
            if self.branch is None:
                raise ValidationError("Branch assignment is required for non-admin users.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Run validation before saving
        super().save(*args, **kwargs)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_branch_manager(self):
        return self.role == 'branch_manager'

    @property
    def is_cashier(self):
        return self.role == 'cashier'

    def has_branch_access(self, branch):
        """
        Check if user has access to a specific branch.
        - Admins have access to all branches
        - Others only to their assigned branch
        """
        if self.is_admin:
            return True
        return self.branch == branch

    def __str__(self):
        if self.is_admin:
            return f"{self.username} (Admin)"
        return f"{self.username} ({self.get_role_display()}) - {self.branch.name if self.branch else 'No Branch'}"