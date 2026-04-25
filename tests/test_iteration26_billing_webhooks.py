"""
Legacy path: iteration 26 billing and Stripe webhook tests were consolidated into the
backend test suite so they run in-process with TestClient and the same MongoDB as CI.

Run:
  cd Pleerity-enterprise/backend
  set PYTHONPATH=.
  python -m pytest tests/test_iteration26_billing_webhooks.py -v
"""
