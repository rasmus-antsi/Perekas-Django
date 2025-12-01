# Maintenance Tasks Setup

This document explains how maintenance tasks (recurring tasks and cleanup) are automated.

## Current Implementation (Recommended)

**Maintenance tasks now run automatically when any family member logs in!**

The system uses a smart approach:
- Runs maintenance tasks when users log in (via middleware)
- Uses session flag to ensure it only runs once per session
- Uses cache (if available) to ensure it only runs once per day globally
- Handles both:
  - Creating recurring tasks that are due
  - Deleting old completed tasks (48+ hours old)

No external cron services needed! The tasks run naturally as users use the app.

## Manual Triggering (Optional)

If you need to manually trigger maintenance tasks, you can use the HTTP endpoint:

```bash
curl -X POST "https://your-app.railway.app/tasks/cron/create-recurring-tasks?secret=YOUR_SECRET_KEY"
```

Or use the management command:
```bash
python manage.py create_recurring_tasks
```

---

## Old Railway Cron Setup (Deprecated - No Longer Needed)

## Option 1: Railway Cron Service (Recommended)

Railway supports cron jobs through their platform. Here's how to set it up:

### Step 1: Add a Cron Service in Railway Dashboard

1. Go to your Railway project dashboard
2. Click "New" → "Cron"
3. Configure the cron job:
   - **Schedule**: `0 0 * * *` (runs daily at 00:00 UTC)
   - **Command**: `curl -X POST https://your-app.railway.app/tasks/cron/create-recurring-tasks?secret=YOUR_SECRET_KEY`
   - Or use the Railway CLI to set up the cron

### Step 2: Set Environment Variable

In your Railway project settings, add:
- **Variable**: `RAILWAY_CRON_SECRET`
- **Value**: A secure random string (generate one with: `openssl rand -hex 32`)

This secret will be used to authenticate cron requests.

### Step 3: Update the Cron Command

Use this command in Railway's cron service:
```bash
curl -X POST "https://your-app.railway.app/tasks/cron/create-recurring-tasks?secret=$RAILWAY_CRON_SECRET"
```

Or set the secret in Railway's environment variables and use:
```bash
curl -X POST -H "X-Railway-Cron-Secret: $RAILWAY_CRON_SECRET" "https://your-app.railway.app/tasks/cron/create-recurring-tasks"
```

## Option 2: External Cron Service (Alternative)

If Railway doesn't have built-in cron support, use an external service:

### Services to Consider:
- **EasyCron**: https://www.easycron.com/
- **cron-job.org**: https://cron-job.org/
- **UptimeRobot**: https://uptimerobot.com/ (for monitoring + cron)

### Setup:
1. Sign up for a cron service
2. Create a new cron job:
   - **URL**: `https://your-app.railway.app/tasks/cron/create-recurring-tasks?secret=YOUR_SECRET_KEY`
   - **Method**: POST
   - **Schedule**: Daily at 00:00 UTC
   - **Headers**: `X-Railway-Cron-Secret: YOUR_SECRET_KEY` (optional, if using query param)

## Option 3: Railway Worker Service

You can also create a separate worker service that runs the command:

1. Add a new service in Railway
2. Set the start command to: `python manage.py create_recurring_tasks`
3. Use Railway's cron service to start/stop this worker at scheduled times

## Testing

Test the endpoint manually:
```bash
curl -X POST "https://your-app.railway.app/tasks/cron/create-recurring-tasks?secret=YOUR_SECRET_KEY"
```

Or test locally:
```bash
python manage.py create_recurring_tasks --dry-run
```

## Security Notes

- Always use the `RAILWAY_CRON_SECRET` environment variable
- Never commit the secret to your repository
- Use HTTPS for all cron requests
- Consider rate limiting if needed

## Monitoring

Check your Railway logs to see when the cron job runs and if there are any errors.

