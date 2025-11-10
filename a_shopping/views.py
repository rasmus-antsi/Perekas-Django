from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def index(request):
    context = {
        'family_name': 'The Taylor Family',
        'to_buy_items': [
            {'name': 'Milk', 'added_by': 'Mom'},
            {'name': 'Bread', 'added_by': 'Dad'},
            {'name': 'Apples', 'added_by': 'Emma'},
        ],
        'in_cart_items': [
            {'name': 'Eggs', 'added_by': 'Sarah'},
        ],
        'active_nav': 'shopping',
    }
    return render(request, 'a_shopping/index.html', context)
