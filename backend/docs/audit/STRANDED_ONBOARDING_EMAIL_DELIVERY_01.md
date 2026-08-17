# Stranded onboarding — email delivery 01

Checkout recovery still uses `send_recovery_payment_email`. Continuation uses the existing recovery notification path.

This programme did **not** send customer email on production. Staging Postmark delivery was previously proven in the June recovery closeout for continuation/payment templates; it was not re-certified against the new release/restart path in this session.

Release and restart does not send a customer email (no continuation path is claimed until they register again).
