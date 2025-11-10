from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from a_family.models import Family

from .models import ShoppingListItem


def index(request):
    user = request.user

    family = None
    if hasattr(user, "families"):
        family = user.families.first()
    if family is None:
        family = Family.objects.filter(owner=user).first()

    if family:
        to_buy_items = ShoppingListItem.objects.filter(family=family, in_cart=False).select_related("added_by")
        in_cart_items = ShoppingListItem.objects.filter(family=family, in_cart=True).select_related("added_by")
    else:
        to_buy_items = ShoppingListItem.objects.none()
        in_cart_items = ShoppingListItem.objects.none()

    context = {
        'family_name': family.name if family else 'Your Family',
        'to_buy_items': to_buy_items,
        'in_cart_items': in_cart_items,
        'to_buy_count': to_buy_items.count(),
        'in_cart_count': in_cart_items.count(),
        'active_nav': 'shopping',
    }
    return render(request, 'a_shopping/index.html', context)
