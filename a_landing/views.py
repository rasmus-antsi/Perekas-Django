from django.shortcuts import render, redirect
from time import time

# Create your views here.
def index(request):
    return render(request, 'a_landing/index.html', {'timestamp': int(time())})


def features(request):
    # Redirect to main page - JavaScript will handle anchor scrolling
    return redirect('a_landing:landing_index')


def about(request):
    # Redirect to main page - JavaScript will handle anchor scrolling
    return redirect('a_landing:landing_index')


def plans(request):
    # Redirect to main page - JavaScript will handle anchor scrolling
    return redirect('a_landing:landing_index')