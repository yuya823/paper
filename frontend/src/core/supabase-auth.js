/** Supabase Auth Client */
import { createClient } from '@supabase/supabase-js';

// These will be set from environment variables or config
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || '';
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

// Local dev mode - skip auth if no Supabase config
export const IS_LOCAL_DEV = !SUPABASE_URL || !SUPABASE_ANON_KEY;

let supabase = null;

if (!IS_LOCAL_DEV) {
  supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: {
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: true, // Important for OAuth redirect handling
    },
  });
}

export { supabase };

/** Get current session token */
export async function getAccessToken() {
  if (IS_LOCAL_DEV) return null;
  const { data } = await supabase.auth.getSession();
  return data?.session?.access_token || null;
}

/** Get current user */
export async function getCurrentUser() {
  if (IS_LOCAL_DEV) return { id: 'dev', email: 'dev@local' };
  const { data, error } = await supabase.auth.getUser();
  if (error) {
    console.warn('[Auth] getCurrentUser error:', error.message);
    return null;
  }
  return data?.user || null;
}

/** Sign up with email */
export async function signUp(email, password) {
  if (IS_LOCAL_DEV) return { user: { id: 'dev', email } };
  const { data, error } = await supabase.auth.signUp({ email, password });
  if (error) throw error;
  return data;
}

/** Sign in with email */
export async function signIn(email, password) {
  if (IS_LOCAL_DEV) return { user: { id: 'dev', email } };
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw error;
  return data;
}

/** Sign in with Google OAuth */
export async function signInWithGoogle() {
  if (IS_LOCAL_DEV) return;
  // Build the redirect URL - use current origin with clean path
  const redirectUrl = `${window.location.origin}${window.location.pathname}`;
  console.log('[Auth] Google OAuth redirect URL:', redirectUrl);
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: redirectUrl,
      queryParams: {
        prompt: 'select_account', // Always show account picker
      },
    },
  });
  if (error) throw error;
  return data;
}

/** Sign out */
export async function signOut() {
  if (IS_LOCAL_DEV) return;
  const { error } = await supabase.auth.signOut();
  if (error) console.error('[Auth] Sign out error:', error);
}

/** Listen to auth state changes */
export function onAuthStateChange(callback) {
  if (IS_LOCAL_DEV) {
    callback('SIGNED_IN', { user: { id: 'dev', email: 'dev@local' } });
    return { unsubscribe: () => {} };
  }
  const { data } = supabase.auth.onAuthStateChange((event, session) => {
    console.log('[Auth] State change:', event, session?.user?.email || 'no user');
    callback(event, session);
  });
  return data.subscription;
}

