// Public values only. The anon key is meant to be public (protected by RLS).
// NEVER put the bot token or the database password here.
const SUPABASE_URL = "https://knuswxrctwdbkqugcgkt.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtudXN3eHJjdHdkYmtxdWdjZ2t0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI3NzY4MDksImV4cCI6MjEwODM1MjgwOX0.QKNYWqYWgf9dEvHaE2a_Wkxl8M7WWXE3cmIQLqe1DI8";
const SB_HEADERS = {
  "apikey": SUPABASE_ANON_KEY,
  "Authorization": "Bearer " + SUPABASE_ANON_KEY,
  "Content-Type": "application/json"
};
