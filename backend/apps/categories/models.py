import uuid

from django.db import models
from django.utils.text import slugify

from apps.organisations.models import Organisation


class Category(models.Model):
    """A node in an org's hierarchical transaction-category taxonomy.

    Categories are always org-scoped: each org owns its own copy of the
    default taxonomy (seeded via ``seeds.seed_default_categories``) so that a
    user can rename/retype a category without affecting any other org —
    honouring the human-in-the-loop principle in the blueprint (§5.2).
    """

    KIND_INCOME = 'income'
    KIND_EXPENSE = 'expense'
    KIND_TRANSFER = 'transfer'
    KIND_CHOICES = [
        (KIND_INCOME, 'Income'),
        (KIND_EXPENSE, 'Expense'),
        (KIND_TRANSFER, 'Transfer'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='categories')
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children'
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_EXPENSE)
    # System categories come from the seeded default taxonomy; custom ones are user-created.
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'transaction_categories'
        unique_together = ('org', 'slug')
        ordering = ('kind', 'name')
        indexes = [
            models.Index(fields=['org', 'kind']),
            models.Index(fields=['org', 'parent']),
        ]
        verbose_name_plural = 'categories'

    def __str__(self) -> str:
        return self.full_path

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def full_path(self) -> str:
        if self.parent_id:
            return f'{self.parent.name} / {self.name}'
        return self.name
