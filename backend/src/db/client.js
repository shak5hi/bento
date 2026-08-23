// src/db/client.js
// Exports a single Supabase client instance using the service-role key.
// This client bypasses Row Level Security — only use server-side, never in browser.

import { createClient } from '@supabase/supabase-js';
import { config } from '../config/index.js';

export const supabase = createClient(
  config.supabase.url,
  config.supabase.serviceRoleKey,
  {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  }
);
