// src/reports/sendEmail.js
// [Lavanya] Sends the weekly health report email via Resend.
// Single responsibility: format the email HTML and call the Resend API.

import { Resend } from 'resend';
import { config } from '../config/index.js';

const resend = new Resend(config.resend.apiKey);

/**
 * Format a trend arrow for display in email.
 * @param {'up'|'down'|'flat'|'unknown'} trend
 * @returns {string}
 */
function trendArrow(trend) {
  if (trend === 'up') return '↑';
  if (trend === 'down') return '↓';
  if (trend === 'flat') return '→';
  return '—';
}

/**
 * Build the HTML body for the weekly report email.
 *
 * @param {object} report - Report content from weeklyReport.js
 * @returns {string} HTML string
 */
function buildEmailHtml(report) {
  const rows = report.projects
    .map(
      (p) => `
      <tr>
        <td style="padding: 8px 12px;">${p.projectName}</td>
        <td style="padding: 8px 12px; text-align: center;">${p.overallScore ?? '—'}/100</td>
        <td style="padding: 8px 12px; text-align: center; color: ${
          p.trend === 'up' ? '#16a34a' : p.trend === 'down' ? '#dc2626' : '#6b7280'
        };">
          ${trendArrow(p.trend)} ${p.delta != null ? Math.abs(Math.round(p.delta)) : ''}
        </td>
      </tr>`
    )
    .join('');

  return `
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; color: #111;">
      <h2 style="margin-bottom: 4px;">🍱 Bento Weekly Health Report</h2>
      <p style="color: #6b7280; font-size: 14px;">Week ending ${new Date(report.weekEnding).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>

      <table style="width: 100%; border-collapse: collapse; margin-top: 24px;">
        <thead>
          <tr style="background: #f3f4f6;">
            <th style="padding: 8px 12px; text-align: left;">Project</th>
            <th style="padding: 8px 12px; text-align: center;">Score</th>
            <th style="padding: 8px 12px; text-align: center;">vs Last Week</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>

      <p style="margin-top: 24px; font-size: 13px; color: #9ca3af;">
        You're receiving this because you have a Bento account. 
        <a href="${config.frontendUrl}" style="color: #6366f1;">View dashboard →</a>
      </p>
    </div>
  `;
}

/**
 * Send the weekly report email to a user.
 *
 * @param {object} params
 * @param {string} params.to      - Recipient email address
 * @param {object} params.report  - Report content object
 * @returns {Promise<void>}
 */
export async function sendWeeklyEmail({ to, report }) {
  const { error } = await resend.emails.send({
    from: config.resend.from,
    to,
    subject: `🍱 Your Bento Weekly Health Report`,
    html: buildEmailHtml(report),
  });

  if (error) {
    throw new Error(`sendWeeklyEmail failed for ${to}: ${error.message}`);
  }
}
