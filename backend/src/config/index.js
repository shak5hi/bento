// src/config/index.js
// Loads and validates every required environment variable.
// Import this instead of calling process.env directly anywhere else.

import dotenv from 'dotenv';
dotenv.config();

const required = [
  'SUPABASE_URL',
  'SUPABASE_SERVICE_ROLE_KEY',
  'GITHUB_CLIENT_ID',
  'GITHUB_CLIENT_SECRET',
  'GITHUB_REDIRECT_URI',
  'GITHUB_WEBHOOK_SECRET',
  'ANTHROPIC_API_KEY',
  'RESEND_API_KEY',
  'EMAIL_FROM',
];

const missing = required.filter((key) => !process.env[key]);
if (missing.length > 0) {
  throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
}

export const config = {
  port: process.env.PORT || 3000,
  nodeEnv: process.env.NODE_ENV || 'development',
  frontendUrl: process.env.FRONTEND_URL || 'http://localhost:4000',
  jwtSecret: process.env.JWT_SECRET || 'dev-secret-change-in-prod',

  supabase: {
    url: process.env.SUPABASE_URL,
    serviceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY,
  },

  github: {
    clientId: process.env.GITHUB_CLIENT_ID,
    clientSecret: process.env.GITHUB_CLIENT_SECRET,
    redirectUri: process.env.GITHUB_REDIRECT_URI,
    webhookSecret: process.env.GITHUB_WEBHOOK_SECRET,
  },

  vercel: {
    apiToken: process.env.VERCEL_API_TOKEN,
  },

  sentry: {
    authToken: process.env.SENTRY_AUTH_TOKEN,
    orgSlug: process.env.SENTRY_ORG_SLUG,
  },

  anthropic: {
    apiKey: process.env.ANTHROPIC_API_KEY,
  },

  resend: {
    apiKey: process.env.RESEND_API_KEY,
    from: process.env.EMAIL_FROM,
  },
};
