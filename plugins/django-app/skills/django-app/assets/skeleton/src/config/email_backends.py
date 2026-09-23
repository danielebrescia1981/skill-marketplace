from django.core.mail.backends.base import BaseEmailBackend


class ProcrastinateEmailBackend(BaseEmailBackend):
    """Queue each message for the worker so requests never wait on SES and failures retry.

    ponytail: no attachments. Store the file and send a link, or use ACTUAL_EMAIL_BACKEND
    directly for the rare message that must carry one.
    """

    def send_messages(self, email_messages):
        from config.tasks import send_email_task

        for message in email_messages:
            if getattr(message, "attachments", None):
                raise ValueError("ProcrastinateEmailBackend cannot queue attachments")
            send_email_task.defer(
                message={
                    "subject": message.subject,
                    "body": message.body,
                    "from_email": message.from_email,
                    "to": list(message.to),
                    "cc": list(message.cc),
                    "bcc": list(message.bcc),
                    "reply_to": list(message.reply_to),
                    "headers": dict(message.extra_headers),
                    "alternatives": [list(a) for a in getattr(message, "alternatives", [])],
                }
            )
        return len(email_messages)
