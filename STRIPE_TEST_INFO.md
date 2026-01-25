# Stripe Test Endpoints & Credentials

## 🔗 **Stripe Test Webhook URL**

```
https://order-fulfillment-9.preview.emergentagent.com/api/webhooks/stripe
```

## 🔑 **Stripe Test Credentials**

### Publishable Key (Frontend)
```
pk_test_51Rn2ZeCF0O5oqdUz22rsivnShQkNwvLz2CLmBM8b6gJu8UdX7kKfKKiXe32pmRIQQEYIyV3hOlAmK5SYcBCcNK5x0051MT3lP1
```

### Secret Key (Backend - Already Configured)
```
sk_test_51Rn2ZeCF0O5oqdUz20lK4vPXKWW7cOMErNLcwup5sN4APWgsaP5eEZVqe6gmVKGc5Jz67LNqgs6zq5YphYGPfuCA00eYP6G2RN
```

### Webhook Secret (Already Configured)
```
whsec_jgG1IvSxCpaJM6maQQEhoOeM4YLU4R9x
```

## 💳 **Stripe Test Cards**

### Successful Payment
```
Card: 4242 4242 4242 4242
Exp: Any future date (e.g., 12/34)
CVC: Any 3 digits (e.g., 123)
ZIP: Any ZIP code
```

### Declined Payment
```
Card: 4000 0000 0000 0002
```

### Requires Authentication (3D Secure)
```
Card: 4000 0025 0000 3155
```

## 🔧 **Testing Stripe Webhooks Locally**

### Option 1: Use Stripe CLI
```bash
stripe listen --forward-to https://order-fulfillment-9.preview.emergentagent.com/api/webhooks/stripe
```

### Option 2: Configure in Stripe Dashboard
1. Go to: https://dashboard.stripe.com/test/webhooks
2. Add endpoint: `https://order-fulfillment-9.preview.emergentagent.com/api/webhooks/stripe`
3. Select events:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `invoice.payment_failed`

## 📋 **Test Payment Flows**

### CVP Subscription Purchase
```
URL: https://order-fulfillment-9.preview.emergentagent.com/pricing
Plans: Starter, Growth, Enterprise
```

### Document Service Purchase
```
URL: https://order-fulfillment-9.preview.emergentagent.com/services
Services: Document packs, Market Research, AI Workflow
```

### ClearForm Credits
```
URL: https://order-fulfillment-9.preview.emergentagent.com/clearform/credits
```

## 🌐 **Backend API Base URL**
```
https://order-fulfillment-9.preview.emergentagent.com
```

All API endpoints are prefixed with `/api/`
Example: `https://order-fulfillment-9.preview.emergentagent.com/api/health`
