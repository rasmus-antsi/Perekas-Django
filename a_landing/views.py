from django.shortcuts import render, redirect
from time import time
from a_api.meta_capi import (
    MetaCapiConfigError,
    MetaCapiSendError,
    build_event_payload,
    build_user_data,
    default_event_id,
    default_event_time,
    send_events_to_meta,
)


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _send_view_content(request):
    client_ip = _client_ip(request)
    client_user_agent = request.META.get('HTTP_USER_AGENT', '')
    email = request.user.email if getattr(request, 'user', None) and request.user.is_authenticated else None
    user_data = build_user_data(email, client_ip, client_user_agent)
    payload = build_event_payload(
        event_name='ViewContent',
        event_time=default_event_time(),
        event_source_url=request.build_absolute_uri(),
        action_source='website',
        event_id=default_event_id(),
        user_data=user_data,
    )
    try:
        send_events_to_meta([payload])
    except (MetaCapiConfigError, MetaCapiSendError, Exception):
        pass


# Create your views here.
def index(request):
    _send_view_content(request)
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


def privacy_policy(request):
    return render(request, 'a_landing/privacy_policy.html')


def terms_of_service(request):
    return render(request, 'a_landing/terms_of_service.html')