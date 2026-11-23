# src/db/

**Owner: Shared**

This folder contains everything related to the database layer.

## Files

| File | Purpose |
|------|---------|
| `schema.sql` | Run this once against your Supabase project to create all tables. Never edit production schema without a migration. |
| `client.js` | Exports a singleton Supabase client using the service-role key. Import `{ supabase }` from here — never create a second client. |

## Rules

- **Never write SQL queries here.** Queries live in the feature files that own them (integrations, scoring, etc.).
- **Never import `client.js` in frontend code.** It uses the service-role key which bypasses RLS.
- To run the schema: paste `schema.sql` into the Supabase SQL editor, or use `supabase db push`.
