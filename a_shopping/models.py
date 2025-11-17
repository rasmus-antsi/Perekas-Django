from django.db import models

from a_family.models import Family

class ShoppingListItem(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    family = models.ForeignKey(Family, on_delete=models.CASCADE, db_index=True)
    added_by = models.ForeignKey('a_family.User', on_delete=models.CASCADE, db_index=True)
    in_cart = models.BooleanField(default=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shopping_shoppinglistitem'
        verbose_name = 'shopping list item'
        verbose_name_plural = 'shopping list items'
        ordering = ['in_cart', '-created_at', 'name']
        indexes = [
            models.Index(fields=['family', 'in_cart']),
        ]

    def __str__(self):
        return self.name
