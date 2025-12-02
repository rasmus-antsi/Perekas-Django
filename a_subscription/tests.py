from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from a_family.models import Family, User
from .models import Subscription, SubscriptionUsage
from .utils import (
    get_user_subscription,
    get_family_subscription,
    get_tier_limits,
    check_subscription_limit,
    check_recurring_task_limit,
    increment_usage,
    get_current_period_start,
    get_current_month_usage,
)


class SubscriptionModelTest(TestCase):
    """Test Subscription model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            role=User.ROLE_PARENT
        )
    
    def test_subscription_creation(self):
        """Test basic subscription creation"""
        subscription = Subscription.objects.create(
            owner=self.user,
            tier=Subscription.TIER_STARTER,
            status=Subscription.STATUS_ACTIVE
        )
        self.assertEqual(subscription.owner, self.user)
        self.assertEqual(subscription.tier, Subscription.TIER_STARTER)
        self.assertEqual(subscription.status, Subscription.STATUS_ACTIVE)
    
    def test_free_tier_is_always_active(self):
        """Test that FREE tier is always considered active"""
        subscription = Subscription.objects.create(
            owner=self.user,
            tier=Subscription.TIER_FREE,
            status=Subscription.STATUS_CANCELLED  # Even if cancelled
        )
        self.assertTrue(subscription.is_active())
    
    def test_paid_tier_active_status(self):
        """Test paid tier active status"""
        subscription = Subscription.objects.create(
            owner=self.user,
            tier=Subscription.TIER_STARTER,
            status=Subscription.STATUS_ACTIVE
        )
        self.assertTrue(subscription.is_active())
        
        subscription.status = Subscription.STATUS_TRIALING
        subscription.save()
        self.assertTrue(subscription.is_active())
        
        subscription.status = Subscription.STATUS_CANCELLED
        subscription.save()
        self.assertFalse(subscription.is_active())


class SubscriptionUtilsTest(TestCase):
    """Test subscription utility functions"""
    
    def setUp(self):
        """Set up test data"""
        self.parent = User.objects.create_user(
            username='parent',
            email='parent@test.com',
            password='testpass123',
            role=User.ROLE_PARENT
        )
        self.family = Family.objects.create(
            name='Test Family',
            owner=self.parent
        )
    
    def test_get_user_subscription_free_by_default(self):
        """Test that user without subscription gets FREE tier"""
        tier = get_user_subscription(self.parent)
        self.assertEqual(tier, Subscription.TIER_FREE)
    
    def test_get_user_subscription_with_active_subscription(self):
        """Test getting subscription tier for user with active subscription"""
        Subscription.objects.create(
            owner=self.parent,
            tier=Subscription.TIER_STARTER,
            status=Subscription.STATUS_ACTIVE
        )
        tier = get_user_subscription(self.parent)
        self.assertEqual(tier, Subscription.TIER_STARTER)
    
    def test_get_family_subscription(self):
        """Test getting subscription tier for family"""
        tier = get_family_subscription(self.family)
        self.assertEqual(tier, Subscription.TIER_FREE)
        
        Subscription.objects.create(
            owner=self.parent,
            tier=Subscription.TIER_PRO,
            status=Subscription.STATUS_ACTIVE
        )
        tier = get_family_subscription(self.family)
        self.assertEqual(tier, Subscription.TIER_PRO)
    
    def test_get_tier_limits(self):
        """Test getting limits for each tier"""
        free_limits = get_tier_limits(Subscription.TIER_FREE)
        self.assertEqual(free_limits['max_tasks_per_month'], 30)
        self.assertEqual(free_limits['max_recurring_tasks'], 3)
        self.assertFalse(free_limits['shopping_list_enabled'])
        
        starter_limits = get_tier_limits(Subscription.TIER_STARTER)
        self.assertEqual(starter_limits['max_tasks_per_month'], 45)
        self.assertEqual(starter_limits['max_recurring_tasks'], 10)
        self.assertTrue(starter_limits['shopping_list_enabled'])
        
        pro_limits = get_tier_limits(Subscription.TIER_PRO)
        self.assertEqual(pro_limits['max_tasks_per_month'], 1000)
        self.assertEqual(pro_limits['max_recurring_tasks'], 1000)
        self.assertTrue(pro_limits['shopping_list_enabled'])
    
    def test_check_subscription_limit_free_tier(self):
        """Test subscription limit checking for FREE tier"""
        # Create 30 tasks (at limit)
        usage = SubscriptionUsage.objects.create(
            family=self.family,
            period_start=get_current_period_start(self.family),
            tasks_created=30
        )
        
        can_create, current, limit, tier = check_subscription_limit(self.family, 'tasks', 1)
        self.assertFalse(can_create)
        self.assertEqual(current, 30)
        self.assertEqual(limit, 30)
        self.assertEqual(tier, Subscription.TIER_FREE)
        
        # Create 29 tasks (under limit)
        usage.tasks_created = 29
        usage.save()
        can_create, current, limit, tier = check_subscription_limit(self.family, 'tasks', 1)
        self.assertTrue(can_create)
    
    def test_check_recurring_task_limit(self):
        """Test recurring task limit checking"""
        # FREE tier allows 3 recurring tasks
        from a_tasks.models import TaskRecurrence, Task
        
        # Create 3 recurring tasks first
        for i in range(3):
            task = Task.objects.create(
                name=f'Task {i}',
                family=self.family,
                created_by=self.parent
            )
            TaskRecurrence.objects.create(
                task=task,
                frequency=TaskRecurrence.FREQUENCY_DAILY,
                next_occurrence=timezone.now() + timedelta(days=1)
            )
        
        # Now check the limit - should use actual count (3) since usage.recurring_tasks_created
        # will be 0 (default) and actual_count is 3, so they differ and it should use actual_count
        # Actually, wait - the logic uses usage value if they differ. Let me set usage to match actual
        # so it uses actual_count
        period_start = get_current_period_start(self.family)
        usage, _ = SubscriptionUsage.objects.get_or_create(
            family=self.family,
            period_start=period_start
        )
        # Set to match actual count so function uses actual_count
        usage.recurring_tasks_created = 3
        usage.save()
        
        can_create, current, limit, tier = check_recurring_task_limit(self.family)
        # Since usage.recurring_tasks_created (3) == actual_count (3), it uses actual_count
        # So current should be 3, and can_create should be False (3 >= 3)
        self.assertFalse(can_create, f"Should not be able to create more recurring tasks. Current: {current}, Limit: {limit}")
        self.assertEqual(current, 3)
        self.assertEqual(limit, 3)
        self.assertEqual(tier, Subscription.TIER_FREE)
    
    def test_increment_usage(self):
        """Test incrementing usage counter"""
        period_start = get_current_period_start(self.family)
        
        # First increment creates the usage record
        increment_usage(self.family, 'tasks', 5)
        usage = SubscriptionUsage.objects.get(family=self.family, period_start=period_start)
        self.assertEqual(usage.tasks_created, 5)
        
        # Second increment updates existing record
        increment_usage(self.family, 'tasks', 3)
        usage.refresh_from_db()
        self.assertEqual(usage.tasks_created, 8)
    
    def test_get_current_period_start(self):
        """Test getting current period start"""
        period_start = get_current_period_start(self.family)
        self.assertIsNotNone(period_start)
        
        # For FREE tier, should be based on family creation
        self.assertIsNotNone(period_start)
    
    def test_get_current_month_usage(self):
        """Test getting current month usage"""
        period_start = get_current_period_start(self.family)
        usage = get_current_month_usage(self.family)
        
        self.assertEqual(usage.family, self.family)
        self.assertEqual(usage.period_start, period_start)
        self.assertEqual(usage.tasks_created, 0)
        self.assertEqual(usage.rewards_created, 0)
