from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, 'a_landing/index.html')


def features(request):
    return render(request, 'a_landing/features.html')


def about(request):
    return render(request, 'a_landing/about.html')


def plans(request):
    return render(request, 'a_landing/plans.html')