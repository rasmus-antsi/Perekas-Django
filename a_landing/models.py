from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ReviewFormSubmission(models.Model):
    """
    Model to store review form submissions from users who created accounts
    but didn't add members or create content.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='review_submissions',
        help_text="User who submitted the review (if authenticated)"
    )
    email = models.EmailField(
        help_text="Email address of the submitter"
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of the submitter (optional)"
    )
    
    # Questions about account creation
    why_created_account = models.TextField(
        help_text="Why did you create an account?"
    )
    
    # Questions about usage
    added_family_members = models.BooleanField(
        default=False,
        help_text="Did you add any family members?"
    )
    created_tasks = models.BooleanField(
        default=False,
        help_text="Did you create any tasks?"
    )
    created_rewards = models.BooleanField(
        default=False,
        help_text="Did you create any rewards?"
    )
    created_shopping_lists = models.BooleanField(
        default=False,
        help_text="Did you create any shopping lists?"
    )
    
    # Feedback
    what_prevented_usage = models.TextField(
        blank=True,
        help_text="What prevented you from using the app?"
    )
    feedback = models.TextField(
        blank=True,
        help_text="Any additional feedback or suggestions?"
    )
    
    # Metadata
    submitted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        db_table = 'landing_review_form_submission'
        verbose_name = 'review form submission'
        verbose_name_plural = 'review form submissions'
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"Review from {self.email} - {self.submitted_at.strftime('%Y-%m-%d %H:%M')}"
