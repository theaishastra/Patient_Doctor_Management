from supabase import create_client, Client
from config import settings

# Anon client for standard operations (respects Row Level Security)
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# Admin client for superuser/system operations (bypasses Row Level Security)
supabase_admin: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
