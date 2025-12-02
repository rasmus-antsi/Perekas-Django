from django.test import TestCase

from a_family.models import Family, User
from .models import Reward


class RewardModelTest(TestCase):
    """Test Reward model functionality"""
    
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
            role=User.ROLE_CHILD
        )
        self.family = Family.objects.create(
            name='Test Family',
            owner=self.parent
        )
        self.family.members.add(self.child)
    
    def test_reward_creation(self):
        """Test basic reward creation"""
        reward = Reward.objects.create(
            name='Test Reward',
            description='A test reward',
            points=50,
            family=self.family,
            created_by=self.parent
        )
        self.assertEqual(reward.name, 'Test Reward')
        self.assertEqual(reward.description, 'A test reward')
        self.assertEqual(reward.points, 50)
        self.assertEqual(reward.family, self.family)
        self.assertEqual(reward.created_by, self.parent)
        self.assertFalse(reward.claimed)
        self.assertIsNone(reward.claimed_by)
    
    def test_reward_claiming(self):
        """Test reward claiming flow"""
        reward = Reward.objects.create(
            name='Test Reward',
            points=50,
            family=self.family,
            created_by=self.parent
        )
        
        # Set child points
        self.child.points = 100
        self.child.save()
        
        # Claim reward
        reward.claimed = True
        reward.claimed_by = self.child
        reward.save()
        
        self.assertTrue(reward.claimed)
        self.assertEqual(reward.claimed_by, self.child)
    
    def test_reward_str(self):
        """Test reward string representation"""
        reward = Reward.objects.create(
            name='Test Reward',
            points=50,
            family=self.family,
            created_by=self.parent
        )
        self.assertEqual(str(reward), 'Test Reward')
