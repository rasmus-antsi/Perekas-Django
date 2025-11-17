from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render

from a_family.models import Family
from a_subscription.utils import has_shopping_list_access

from .models import ShoppingListItem


@login_required
def index(request):
    user = request.user

    family = None
    if hasattr(user, "families"):
        family = user.families.first()
    if family is None:
        family = Family.objects.filter(owner=user).first()

    # Check if family has shopping list access
    if family and not has_shopping_list_access(family):
        messages.warning(
            request,
            "Shopping list is only available with Starter or Pro subscription. "
            "Please upgrade your subscription to access this feature."
        )
        return redirect('a_subscription:status')

    if request.method == "POST":
        action = request.POST.get("action")
        if family and action == "add":
            item_name = request.POST.get("name", "").strip()
            if item_name:
                ShoppingListItem.objects.create(
                    name=item_name,
                    family=family,
                    added_by=user,
                )
        elif family and action == "delete":
            item_id = request.POST.get("item_id")
            if item_id:
                ShoppingListItem.objects.filter(id=item_id, family=family).delete()
        elif family and action == "toggle":
            item_id = request.POST.get("item_id")
            if item_id:
                try:
                    item = ShoppingListItem.objects.get(id=item_id, family=family)
                except ShoppingListItem.DoesNotExist:
                    item = None
                if item:
                    set_in_cart = request.POST.get("set_in_cart")
                    if set_in_cart is not None:
                        item.in_cart = set_in_cart.lower() == "true"
                    else:
                        item.in_cart = not item.in_cart
                    item.save(update_fields=["in_cart"])
        return redirect("a_shopping:index")

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
        'has_family': family is not None,
        'active_nav': 'shopping',
    }
    return render(request, 'a_shopping/index.html', context)
