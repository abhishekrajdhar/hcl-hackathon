"use client";

import { useCallback, useEffect, useState } from "react";
import { auth, getToken, setToken } from "@/lib/api";
import type { User } from "@/lib/types";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      if (getToken()) {
        try {
          setUser(await auth.me());
        } catch {
          setToken(null);
        }
      }
      setReady(true);
    })();
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const res = await auth.login(email, password);
    setUser(res.user);
    return res.user;
  }, []);

  const signOut = useCallback(() => {
    auth.logout();
    setUser(null);
  }, []);

  return { user, ready, signIn, signOut };
}
