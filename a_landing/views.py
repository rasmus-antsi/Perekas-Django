from django.shortcuts import render
from time import time

# Create your views here.
def index(request):
    return render(request, 'a_landing/index.html', {'timestamp': int(time())})


def features(request):
    return render(request, 'a_landing/features.html')


def about(request):
    return render(request, 'a_landing/about.html')


def plans(request):
    return render(request, 'a_landing/plans.html')