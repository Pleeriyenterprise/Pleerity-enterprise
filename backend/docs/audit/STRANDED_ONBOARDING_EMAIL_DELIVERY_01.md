# Stranded onboarding — email delivery 01

Checkout recovery still uses `send_recovery_payment_email`. Continuation uses the existing recovery notification path.

Staging Postmark: replacement recovery checkout with `send_customer_email=true` produced `email_sent: true`, audit `EMAIL_SENT` / `EMAIL_DELIVERED`, and message-log `status: DELIVERED` for `so.promo.202608171708@yopmail.com` (template `ADMIN_MANUAL`). Customer opening the emailed link and completing payment was not yet proven because Playwright did not fill Stripe’s required card iframe (`PAYMENT METHOD REQUIRED` on a £0.00 repeating-pilot checkout).

Release and restart does not send a customer email (no continuation path is claimed until they register again).
