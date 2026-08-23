# src/reports/

**Owner: Lavanya**

This folder handles weekly engineering health report generation and email delivery.

## Files

| File | Purpose |
|------|---------|
| `weeklyReport.js` | Generates week-over-week score deltas for all projects per user, saves to `reports` table, and calls `sendEmail.js`. Invoked by the Monday cron job in `scheduler.js`. |
| `sendEmail.js` | Formats the HTML email template and sends it via Resend. Single responsibility: email only. |

## Cron schedule

Runs every Monday at 8am UTC: `0 8 * * 1` (configured in `src/jobs/scheduler.js`).

## Email preview

The email includes:
- Project name
- Current overall score
- Delta vs last week (with ↑↓→ arrows and green/red color)
- Link back to the Bento dashboard

## Adding content to the report

1. Modify `buildEmailHtml()` in `sendEmail.js` to add new sections
2. Modify `generateUserReport()` in `weeklyReport.js` to include additional data in `reportContent`
3. The `content` column in `reports` is `jsonb` — add any fields you need

## Resend setup

1. Create an account at https://resend.com (free tier: 100 emails/day)
2. Verify your sending domain
3. Copy the API key to `RESEND_API_KEY` in `.env`
4. Set `EMAIL_FROM` to your verified sender address
