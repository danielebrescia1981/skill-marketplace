# Billing — Stripe subscriptions

**Load:** only when Q4 = yes. Use the `stripe:stripe-best-practices` skill for current API specifics. This module covers only the house structure.

## Shape

- **Raw `stripe` SDK, not dj-stripe.** Mirror only what you need: appsfolio, meetingsignals and refractions all do this.
- A `billing` app (or `subscriptions`) with:
  - `Subscription`: one-to-one with the **billable party** (Tenant when tenant-based, else User). Fields: `stripe_customer_id` (unique, null), `stripe_subscription_id` (unique, null), `status` (choices mirroring Stripe's), `current_period_end`, `plan`. `is_active` = status in `{active, trialing}`.
  - `StripeWebhookEvent`: `event_id` unique, `type`, `processed_at`. Idempotency.
  - `Plan` / prices: in settings (`PRICING` dict exposed through a context processor) for 1–3 plans. Move to a model, or a nested `stripe/` sync tool with its own justfile and `config.yaml` (appsfolio), once plans differ per environment.
- Views: `checkout/` (Stripe Checkout session), `checkout/success/`, `checkout/cancel/`, `portal/` (Customer Portal for card, plan and cancel; don't build these screens), `webhook/`.
- Gating: `@paid_required` decorator / mixin. Logged out → login; unpaid → pricing page. With tenancy, `request.tenant.subscription.is_active`. Restrict billing views to the billing role (`@user_passes_test(is_billing_manager)`).

## Webhook

The only source of truth for subscription state. Success-page redirects just say "thanks".

```python
RETRYABLE = (stripe.error.APIConnectionError, stripe.error.RateLimitError, DatabaseError)
HANDLERS = {
    "checkout.session.completed": on_checkout_completed,
    "customer.subscription.created": sync_subscription,
    "customer.subscription.updated": sync_subscription,
    "customer.subscription.deleted": sync_subscription,
    "invoice.paid": on_invoice_paid,
    "invoice.payment_failed": on_payment_failed,
}

@csrf_exempt
@require_POST
def webhook(request):
    try:
        event = stripe.Webhook.construct_event(request.body, request.headers["Stripe-Signature"],
                                               settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, KeyError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)
    _, created = StripeWebhookEvent.objects.get_or_create(event_id=event.id, defaults={"type": event.type})
    if not created:
        return HttpResponse(status=200)                      # duplicate delivery
    try:
        if handler := HANDLERS.get(event.type):
            handler(event.data.object)
    except RETRYABLE:
        StripeWebhookEvent.objects.filter(event_id=event.id).delete()
        return HttpResponse(status=500)                      # Stripe redelivers
    except Exception:
        logger.exception("stripe webhook %s failed", event.type)   # ack: retrying a bug won't fix it
    return HttpResponse(status=200)
```

- `STRIPE_WEBHOOK_SECRET` is a **required secret** (foundation.md `_required`). An empty secret means an unverified webhook.
- `sync_subscription` re-fetches the subscription from Stripe rather than trusting event order.
- Exempt `/billing/webhook/` from tenant middleware and rate limits. With tenancy, the handler finds the tenant via `stripe_customer_id` on the admin alias, then acts inside `tenant_context`.
- Heavy follow-ups (provisioning, welcome email) → `.defer()`.
- Record counts and durations if `/metrics` exists.

## Dev and ops

- `just dev` runs `stripe listen --forward-to https://myapp.localhost/billing/webhook/`. Put the `whsec_…` it prints into `.env`.
- `manage.py sync_subscription <id>` and a `reconcile` command (refractions runs one as a manual GitHub workflow over SSH) fix drift after an outage.
- Test mode on dev/test, live mode on prod. `LAUNCH.md` 🔴 item: switch prod keys, register the prod webhook endpoint and its secret, and set up Customer Portal config in live mode.
- Tests: `tests/test_stripe_webhooks.py` with signed payloads (`stripe.WebhookSignature` helpers or a fixture that signs), covering the duplicate event, the retryable error → 500, and the handler bug → 200.
