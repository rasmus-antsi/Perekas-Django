from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from a_family.models import Family
from a_family.emails import send_shopping_item_added_notification
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

    # Check if family has shopping list access (for all users, including children)
    if family and not has_shopping_list_access(family):
        messages.error(
            request,
            "Ostunimekiri on saadaval Starter või Pro paketiga. Palun uuenda tellimust, et seda kasutada."
        )
        # Redirect family owner to subscription settings, others to dashboard
        if family.owner == user:
            return redirect(f"{reverse('a_account:settings')}?section=subscriptions&upgrade=1")
        else:
            referer = request.META.get('HTTP_REFERER')
            # Only redirect to referer if it's from the same site
            if referer and request.build_absolute_uri('/').split('/')[2] in referer:
                return redirect(referer)
            return redirect(reverse('a_dashboard:dashboard'))
    
    # Also check if user has no family
    if not family:
        messages.error(request, "Ostunimekirja kasutamiseks pead olema pere liige.")
        referer = request.META.get('HTTP_REFERER')
        if referer and request.build_absolute_uri('/').split('/')[2] in referer:
            return redirect(referer)
        return redirect(reverse('a_family:onboarding'))

    if request.method == "POST":
        action = request.POST.get("action")
        if family and action == "add":
            item_name = request.POST.get("name", "").strip()
            if item_name:
                item = ShoppingListItem.objects.create(
                    name=item_name,
                    family=family,
                    added_by=user,
                )
                # Send notification email
                try:
                    send_shopping_item_added_notification(request, item)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to send shopping item added notification: {e}", exc_info=True)
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
        'to_buy_items': to_buy_items,
        'in_cart_items': in_cart_items,
        'to_buy_count': to_buy_items.count(),
        'in_cart_count': in_cart_items.count(),
        'has_family': family is not None,
        'active_nav': 'shopping',
    }
    return render(request, 'a_shopping/index.html', context)
