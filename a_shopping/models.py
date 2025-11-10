from django.db import models
from a_family.models import Family
from django.contrib.auth.models import User

# Create your models here.
class ShoppingListItem(models.Model):
    name = models.CharField(max_length=255)
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)
    in_cart = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
