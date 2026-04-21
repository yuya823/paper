/** Supabase Auth Client */
import { createClient } from '@supabase/supabase-js';

// These will be set from environment variables or config
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || '';
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

// Local dev mode - skip auth if no Supabase config
export const IS_LOCAL_DEV = !SUPABASE_URL || !SUPABASE_ANON_KEY;

let supabase = null;

if (!IS_LOCAL_DEV) {
  supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
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
  const { data } = await supabase.auth.getUser();
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
  const { error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: window.location.origin },
  });
  if (error) throw error;
}

/** Sign out */
export async function signOut() {
  if (IS_LOCAL_DEV) return;
  await supabase.auth.signOut();
}

/** Listen to auth state changes */
export function onAuthStateChange(callback) {
  if (IS_LOCAL_DEV) {
    callback('SIGNED_IN', { user: { id: 'dev', email: 'dev@local' } });
    return { unsubscribe: () => {} };
  }
  const { data } = supabase.auth.onAuthStateChange((event, session) => {
    callback(event, session);
  });
  return data.subscription;
}
