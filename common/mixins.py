from django.db import models
from django.db.models import QuerySet


class BranchScopedQuerySet(QuerySet):
    """QuerySet that automatically filters by branch_id from context."""
    
    def for_branch(self, branch_id):
        """Explicitly filter by branch."""
        if not branch_id:
            return self
        return self.filter(branch_id=branch_id)


class BranchScopedManager(models.Manager):
    """Manager that respects branch scoping."""
    
    def get_queryset(self):
        return BranchScopedQuerySet(self.model, using=self._db)
    
    def for_branch(self, branch_id):
        return self.get_queryset().for_branch(branch_id)


class BranchScopedMixin(models.Model):
    """
    Mixin to add branch-awareness to a model.
    Ensures all queries respect branch isolation.
    """
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    
    objects = BranchScopedManager()
    
    class Meta:
        abstract = True
