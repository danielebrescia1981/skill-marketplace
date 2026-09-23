from django.core.mail import EmailMultiAlternatives, mailers
from procrastinate.contrib.django import app


@app.task(queue="emails", retry=5, name="send_email")
def send_email_task(message: dict) -> None:
    """Send one queued message through the `transport` mailer (the default mailer would re-queue it)."""
    email = EmailMultiAlternatives(
        subject=message["subject"],
        body=message["body"],
        from_email=message["from_email"],
        to=message["to"],
        cc=message.get("cc", []),
        bcc=message.get("bcc", []),
        reply_to=message.get("reply_to", []),
        headers=message.get("headers", {}),
        connection=mailers["transport"],
    )
    for content, mimetype in message.get("alternatives", []):
        email.attach_alternative(content, mimetype)
    email.send()
