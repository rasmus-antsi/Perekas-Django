"""
Utility functions for calculating recurring task occurrences.
Recurring tasks start from the due_date, not the creation date.
"""
from datetime import timedelta, datetime as dt
from django.utils import timezone


def calculate_next_occurrence(due_date, frequency, interval=1, day_of_week=None, day_of_month=None):
    """
    Calculate the next occurrence date for a recurring task.
    Recurring tasks recur on the specified day of week (weekly) or day of month (monthly).
    
    Args:
        due_date: The original due date (or current due date for existing tasks)
        frequency: 'daily', 'business_daily', 'every_other_day', 'weekly', or 'monthly'
        interval: Interval multiplier (default 1)
        day_of_week: 0-6 (Monday-Sunday) for weekly recurrence (optional, uses due_date if not provided)
        day_of_month: 1-31 for monthly recurrence (optional, uses due_date if not provided)
    
    Returns:
        tuple: (next_due_date, next_occurrence_datetime)
    """
    now = timezone.now()
    today = now.date()
    
    if frequency == 'daily':
        if due_date:
            next_due_date = due_date + timedelta(days=interval)
        else:
            next_due_date = today + timedelta(days=interval)
    elif frequency == 'business_daily':
        # Recur on weekdays only (Monday-Friday)
        base_date = due_date if due_date else today
        next_due_date = base_date + timedelta(days=1)
        # Skip weekends - if next day is Saturday or Sunday, move to next Monday
        while next_due_date.weekday() >= 5:  # Saturday=5, Sunday=6
            next_due_date += timedelta(days=1)
    elif frequency == 'every_other_day':
        # Recur every 2 days
        if due_date:
            next_due_date = due_date + timedelta(days=2)
        else:
            next_due_date = today + timedelta(days=2)
    elif frequency == 'weekly':
        # Use specified day_of_week or derive from due_date
        if day_of_week is not None:
            # Find next occurrence of this day of week
            # day_of_week: 0=Monday, 6=Sunday
            base_date = due_date if due_date else today
            current_weekday = base_date.weekday()  # 0=Monday, 6=Sunday
            days_ahead = day_of_week - current_weekday
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7 * interval
            # If days_ahead is positive and less than 7*interval, use it (it's this week)
            # Otherwise, it's already set correctly for next interval
            next_due_date = base_date + timedelta(days=days_ahead)
        elif due_date:
            # Use due_date's day of week
            next_due_date = due_date + timedelta(weeks=interval)
        else:
            # Default to next week same day
            next_due_date = today + timedelta(weeks=interval)
    elif frequency == 'monthly':
        # Use specified day_of_month or derive from due_date
        if day_of_month is not None:
            # Find next occurrence of this day of month
            year = today.year
            month = today.month
            
            # Try this month first
            try:
                candidate_date = dt(year, month, day_of_month).date()
                if candidate_date > today:
                    next_due_date = candidate_date
                else:
                    # Move to next month
                    month += interval
                    if month > 12:
                        month -= 12
                        year += 1
                    # Handle day overflow
                    try:
                        next_due_date = dt(year, month, day_of_month).date()
                    except ValueError:
                        # Day doesn't exist in target month, use last day
                        if month == 2:
                            if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                                day = 29
                            else:
                                day = 28
                        elif month in [4, 6, 9, 11]:
                            day = 30
                        else:
                            day = 31
                        next_due_date = dt(year, month, day).date()
            except ValueError:
                # Day doesn't exist this month, try next month
                month += interval
                if month > 12:
                    month -= 12
                    year += 1
                try:
                    next_due_date = dt(year, month, day_of_month).date()
                except ValueError:
                    # Use last day of month
                    if month == 2:
                        if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                            day = 29
                        else:
                            day = 28
                    elif month in [4, 6, 9, 11]:
                        day = 30
                    else:
                        day = 31
                    next_due_date = dt(year, month, day).date()
        elif due_date:
            # Use due_date's day of month
            year = due_date.year
            month = due_date.month
            day = due_date.day
            
            # Add months
            month += interval
            while month > 12:
                month -= 12
                year += 1
            
            # Handle day overflow
            try:
                next_due_date = due_date.replace(year=year, month=month)
            except ValueError:
                # Day doesn't exist in target month, use last day of month
                if month == 2:
                    if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                        day = 29
                    else:
                        day = 28
                elif month in [4, 6, 9, 11]:
                    day = 30
                else:
                    day = 31
                next_due_date = due_date.replace(year=year, month=month, day=day)
        else:
            # Default to next month same day
            month = today.month + interval
            year = today.year
            while month > 12:
                month -= 12
                year += 1
            try:
                next_due_date = dt(year, month, today.day).date()
            except ValueError:
                # Use last day of month
                if month == 2:
                    if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                        day = 29
                    else:
                        day = 28
                elif month in [4, 6, 9, 11]:
                    day = 30
                else:
                    day = 31
                next_due_date = dt(year, month, day).date()
    else:
        # Default to daily
        next_due_date = (due_date or today) + timedelta(days=1)
    
    # Create datetime for next_occurrence (start of day)
    next_occurrence = timezone.make_aware(
        dt.combine(next_due_date, dt.min.time())
    )
    
    return next_due_date, next_occurrence

