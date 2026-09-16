'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

const STORAGE_KEY = 'stock-admin-auth';
const EXPECTED = process.env.NEXT_PUBLIC_ADMIN_PASSWORD;

export function LoginGate({ children }) {
  const [checked, setChecked] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (typeof window !== 'undefined' && window.localStorage.getItem(STORAGE_KEY) === '1') {
      setAuthed(true);
    }
    setChecked(true);
  }, []);

  function handleSubmit(e) {
    e.preventDefault();
    if (!EXPECTED) {
      setError('Admin password is not configured. Set NEXT_PUBLIC_ADMIN_PASSWORD.');
      return;
    }
    if (password === EXPECTED) {
      window.localStorage.setItem(STORAGE_KEY, '1');
      setAuthed(true);
      setError('');
    } else {
      setError('Incorrect password');
      setPassword('');
    }
  }

  function handleLogout() {
    window.localStorage.removeItem(STORAGE_KEY);
    setAuthed(false);
    setPassword('');
  }

  if (!checked) return null;

  if (!authed) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-muted/20 p-4">
        <Card className="w-full max-w-sm border-2">
          <CardHeader>
            <CardTitle className="text-2xl">Stock Tracker Admin</CardTitle>
            <CardDescription>Enter the admin password to continue.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <Input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoFocus
                aria-invalid={error ? true : undefined}
              />
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" className="w-full">Unlock</Button>
            </form>
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <>
      {children}
      <button
        type="button"
        onClick={handleLogout}
        className="fixed bottom-4 right-4 text-xs text-muted-foreground hover:text-foreground bg-muted/50 hover:bg-muted px-3 py-1.5 rounded-md border transition-colors"
      >
        Log out
      </button>
    </>
  );
}
