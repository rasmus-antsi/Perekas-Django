import logging
import threading

from allauth.account.adapter import DefaultAccountAdapter


logger = logging.getLogger(__name__)


class AsyncAccountAdapter(DefaultAccountAdapter):
    """
    Account adapter that dispatches transactional emails on a background thread
    so that signup/login views respond immediately, even if SMTP is slow.
    """

    def send_mail(self, template_prefix, email, context):
        def _runner():
            try:
                super(AsyncAccountAdapter, self).send_mail(template_prefix, email, context)
            except Exception:
                logger.exception("Failed to send account email to %s", email)

        threading.Thread(target=_runner, daemon=True).start()

