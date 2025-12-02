from django.test import TestCase
from django.contrib.auth import get_user_model

from .models import Family, User


class UserModelTest(TestCase):
    """Test User model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.parent = User.objects.create_user(
            username='parent',
            email='parent@test.com',
            password='testpass123',
            role=User.ROLE_PARENT,
            first_name='Parent',
            last_name='User'
        )
        self.child = User.objects.create_user(
            username='child',
            email='child@test.com',
            password='testpass123',
            role=User.ROLE_CHILD,
            first_name='Child',
            last_name='User'
        )
    
    def test_user_creation(self):
        """Test basic user creation"""
        self.assertEqual(self.parent.username, 'parent')
        self.assertEqual(self.parent.role, User.ROLE_PARENT)
        self.assertEqual(self.child.role, User.ROLE_CHILD)
    
    def test_user_display_name(self):
        """Test user display name"""
        # User with first and last name
        self.assertEqual(self.parent.get_display_name(), 'Parent User')
        
        # User with only first name
        child2 = User.objects.create_user(
            username='child2',
            email='child2@test.com',
            password='testpass123',
            role=User.ROLE_CHILD,
            first_name='Child2'
        )
        self.assertEqual(child2.get_display_name(), 'Child2')
        
        # User with only username
        child3 = User.objects.create_user(
            username='child3',
            email='child3@test.com',
            password='testpass123',
            role=User.ROLE_CHILD
        )
        self.assertEqual(child3.get_display_name(), 'child3')
    
    def test_user_points(self):
        """Test user points system"""
        self.assertEqual(self.child.points, 0)
        
        self.child.points = 100
        self.child.save()
        self.assertEqual(self.child.points, 100)
        
        # Points should not go below 0 (database constraint)
        # Setting negative points would violate CHECK constraint
        # In practice, use max(0, points) when deducting
        self.child.points = 0
        self.child.save()
        self.assertEqual(self.child.points, 0)


class FamilyModelTest(TestCase):
    """Test Family model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.parent = User.objects.create_user(
            username='parent',
            email='parent@test.com',
            password='testpass123',
            role=User.ROLE_PARENT
        )
        self.child1 = User.objects.create_user(
            username='child1',
            email='child1@test.com',
            password='testpass123',
            role=User.ROLE_CHILD
        )
        self.child2 = User.objects.create_user(
            username='child2',
            email='child2@test.com',
            password='testpass123',
            role=User.ROLE_CHILD
        )
    
    def test_family_creation(self):
        """Test basic family creation"""
        family = Family.objects.create(
            name='Test Family',
            owner=self.parent
        )
        self.assertEqual(family.name, 'Test Family')
        self.assertEqual(family.owner, self.parent)
    
    def test_family_members(self):
        """Test adding members to family"""
        family = Family.objects.create(
            name='Test Family',
            owner=self.parent
        )
        
        family.members.add(self.child1, self.child2)
        
        self.assertEqual(family.members.count(), 2)
        self.assertIn(self.child1, family.members.all())
        self.assertIn(self.child2, family.members.all())
    
    def test_family_owner_not_in_members(self):
        """Test that owner is not automatically in members"""
        family = Family.objects.create(
            name='Test Family',
            owner=self.parent
        )
        
        # Owner should not be in members by default
        self.assertNotIn(self.parent, family.members.all())
    
    def test_family_str(self):
        """Test family string representation"""
        family = Family.objects.create(
            name='Test Family',
            owner=self.parent
        )
        self.assertEqual(str(family), 'Test Family')
