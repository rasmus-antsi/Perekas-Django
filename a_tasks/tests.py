from django.test import TestCase
from django.utils import timezone
from datetime import date, timedelta

from a_family.models import Family, User
from .models import Task, TaskRecurrence


class TaskModelTest(TestCase):
    """Test Task model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.parent = User.objects.create_user(
            username='parent',
            email='parent@test.com',
            password='testpass123',
            role=User.ROLE_PARENT
        )
        self.child = User.objects.create_user(
            username='child',
            email='child@test.com',
            password='testpass123',
            role=User.ROLE_CHILD,
            first_name='Test'
        )
        self.family = Family.objects.create(
            name='Test Family',
            owner=self.parent
        )
        self.family.members.add(self.child)
    
    def test_task_creation(self):
        """Test basic task creation"""
        task = Task.objects.create(
            name='Test Task',
            family=self.family,
            created_by=self.parent,
            assigned_to=self.child,
            priority=Task.PRIORITY_HIGH,
            points=50
        )
        self.assertEqual(task.name, 'Test Task')
        self.assertEqual(task.family, self.family)
        self.assertEqual(task.created_by, self.parent)
        self.assertEqual(task.assigned_to, self.child)
        self.assertEqual(task.priority, Task.PRIORITY_HIGH)
        self.assertEqual(task.points, 50)
        self.assertFalse(task.completed)
        self.assertFalse(task.approved)
    
    def test_task_is_in_progress(self):
        """Test is_in_progress property"""
        task = Task.objects.create(
            name='Test Task',
            family=self.family,
            created_by=self.parent,
            assigned_to=self.child
        )
        self.assertFalse(task.is_in_progress)
        
        task.started_at = timezone.now()
        task.save()
        self.assertTrue(task.is_in_progress)
        
        task.completed = True
        task.save()
        self.assertFalse(task.is_in_progress)
    
    def test_task_completion(self):
        """Test task completion flow"""
        task = Task.objects.create(
            name='Test Task',
            family=self.family,
            created_by=self.parent,
            assigned_to=self.child,
            points=50
        )
        
        # Complete task
        task.completed = True
        task.completed_by = self.child
        task.completed_at = timezone.now()
        task.save()
        
        self.assertTrue(task.completed)
        self.assertEqual(task.completed_by, self.child)
        self.assertIsNotNone(task.completed_at)
    
    def test_task_approval(self):
        """Test task approval flow"""
        task = Task.objects.create(
            name='Test Task',
            family=self.family,
            created_by=self.parent,
            assigned_to=self.child,
            points=50,
            completed=True,
            completed_by=self.child
        )
        
        # Approve task
        task.approved = True
        task.approved_by = self.parent
        task.approved_at = timezone.now()
        task.save()
        
        self.assertTrue(task.approved)
        self.assertEqual(task.approved_by, self.parent)
        self.assertIsNotNone(task.approved_at)
    
    def test_task_with_due_date(self):
        """Test task with due date"""
        due_date = date.today() + timedelta(days=7)
        task = Task.objects.create(
            name='Test Task',
            family=self.family,
            created_by=self.parent,
            due_date=due_date
        )
        self.assertEqual(task.due_date, due_date)
    
    def test_task_priority_choices(self):
        """Test task priority choices"""
        task_low = Task.objects.create(
            name='Low Priority',
            family=self.family,
            created_by=self.parent,
            priority=Task.PRIORITY_LOW
        )
        task_medium = Task.objects.create(
            name='Medium Priority',
            family=self.family,
            created_by=self.parent,
            priority=Task.PRIORITY_MEDIUM
        )
        task_high = Task.objects.create(
            name='High Priority',
            family=self.family,
            created_by=self.parent,
            priority=Task.PRIORITY_HIGH
        )
        
        self.assertEqual(task_low.priority, Task.PRIORITY_LOW)
        self.assertEqual(task_medium.priority, Task.PRIORITY_MEDIUM)
        self.assertEqual(task_high.priority, Task.PRIORITY_HIGH)


class TaskRecurrenceModelTest(TestCase):
    """Test TaskRecurrence model functionality"""
    
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
        self.task = Task.objects.create(
            name='Recurring Task',
            family=self.family,
            created_by=self.parent,
            due_date=date.today()
        )
    
    def test_recurrence_creation(self):
        """Test basic recurrence creation"""
        recurrence = TaskRecurrence.objects.create(
            task=self.task,
            frequency=TaskRecurrence.FREQUENCY_DAILY,
            next_occurrence=timezone.now() + timedelta(days=1)
        )
        self.assertEqual(recurrence.task, self.task)
        self.assertEqual(recurrence.frequency, TaskRecurrence.FREQUENCY_DAILY)
        self.assertEqual(recurrence.interval, 1)  # Default
    
    def test_weekly_recurrence_with_day(self):
        """Test weekly recurrence with specific day"""
        recurrence = TaskRecurrence.objects.create(
            task=self.task,
            frequency=TaskRecurrence.FREQUENCY_WEEKLY,
            day_of_week=0,  # Monday
            next_occurrence=timezone.now() + timedelta(days=7)
        )
        self.assertEqual(recurrence.frequency, TaskRecurrence.FREQUENCY_WEEKLY)
        self.assertEqual(recurrence.day_of_week, 0)
    
    def test_monthly_recurrence_with_day(self):
        """Test monthly recurrence with specific day"""
        recurrence = TaskRecurrence.objects.create(
            task=self.task,
            frequency=TaskRecurrence.FREQUENCY_MONTHLY,
            day_of_month=15,
            next_occurrence=timezone.now() + timedelta(days=30)
        )
        self.assertEqual(recurrence.frequency, TaskRecurrence.FREQUENCY_MONTHLY)
        self.assertEqual(recurrence.day_of_month, 15)
    
    def test_recurrence_with_end_date(self):
        """Test recurrence with end date"""
        end_date = date.today() + timedelta(days=30)
        recurrence = TaskRecurrence.objects.create(
            task=self.task,
            frequency=TaskRecurrence.FREQUENCY_DAILY,
            end_date=end_date,
            next_occurrence=timezone.now() + timedelta(days=1)
        )
        self.assertEqual(recurrence.end_date, end_date)
    
    def test_recurrence_cascade_delete(self):
        """Test that recurrence is deleted when task is deleted"""
        recurrence = TaskRecurrence.objects.create(
            task=self.task,
            frequency=TaskRecurrence.FREQUENCY_DAILY,
            next_occurrence=timezone.now() + timedelta(days=1)
        )
        recurrence_id = recurrence.id
        
        self.task.delete()
        
        self.assertFalse(TaskRecurrence.objects.filter(id=recurrence_id).exists())
