"""
Core views for the application.
"""
from django.http import JsonResponse
from django.db import connection


def health_check(request):
    """
    Health check endpoint for monitoring.
    
    Returns:
        JSON response with status and database connectivity check
    """
    try:
        # Check database connectivity
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    status_code = 200 if db_status == "ok" else 503
    
    return JsonResponse({
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
    }, status=status_code)

