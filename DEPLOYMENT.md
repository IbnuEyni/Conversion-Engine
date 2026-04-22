# Render Deployment Guide

## 1. Prepare Repository
- Commit all changes to your GitHub repository
- Ensure `render.yaml`, `Procfile`, and `.env.render` are included

## 2. Deploy to Render
1. Go to https://render.com and sign up (no credit card required)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `conversion-engine` (or your preferred name)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -e .`
   - **Start Command**: `uvicorn agent.main:app --host 0.0.0.0 --port $PORT`

## 3. Set Environment Variables
In Render dashboard, go to Environment tab and add all variables from `.env.render`:

```
OPENROUTER_API_KEY=<your_openrouter_key>
DEV_MODEL=qwen/qwen3-235b-a22b
EVAL_MODEL=anthropic/claude-sonnet-4
RESEND_API_KEY=<your_resend_key>
FROM_EMAIL=onboarding@resend.dev
AT_USERNAME=sandbox
AT_API_KEY=<your_africastalking_key>
HUBSPOT_ACCESS_TOKEN=<your_hubspot_token>
HUBSPOT_PORTAL_ID=<your_portal_id>
CALCOM_API_KEY=<your_calcom_key>
LANGFUSE_SECRET_KEY=<your_langfuse_secret>
LANGFUSE_PUBLIC_KEY=<your_langfuse_public>
LIVE_MODE=false
```

## 4. Update Webhook URLs
After deployment, your app will be available at: `https://YOUR-APP-NAME.onrender.com`

Update these environment variables with your actual URL:
```
REPLY_WEBHOOK_URL=https://YOUR-APP-NAME.onrender.com/webhooks/email/reply
AT_WEBHOOK_URL=https://YOUR-APP-NAME.onrender.com/webhooks/sms/inbound
```

## 5. Register Webhooks
Configure your webhook URLs in each service:

### Resend
- Dashboard → Webhooks → Add webhook
- URL: `https://YOUR-APP-NAME.onrender.com/webhooks/email/reply`
- Events: `email.delivered`, `email.bounced`, `email.complained`

### Africa's Talking
- Dashboard → SMS → Callback URLs
- URL: `https://YOUR-APP-NAME.onrender.com/webhooks/sms/inbound`

### Cal.com
- Settings → Webhooks → Add webhook
- URL: `https://YOUR-APP-NAME.onrender.com/webhooks/calcom/booking`
- Events: `BOOKING_CREATED`, `BOOKING_CANCELLED`

## 6. Test Deployment
- Visit `https://YOUR-APP-NAME.onrender.com/health`
- Check `https://YOUR-APP-NAME.onrender.com/docs` for API documentation
- Test webhook endpoints

## 7. Monitor
- Render provides logs and metrics in the dashboard
- Check Langfuse for observability data
- Monitor HubSpot for CRM sync status