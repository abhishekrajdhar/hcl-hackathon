import type { TokenResponse, User } from "@/lib/types";
import { request, setToken } from "./client";

export async function login(email: string, password: string): Promise<TokenResponse> {
  const res = await request<TokenResponse>("/auth/login", {
    method: "POST",
    auth: false,
    body: { email, password },
  });
  setToken(res.access_token);
  return res;
}

export async function register(
  email: string,
  password: string,
  fullName?: string,
): Promise<TokenResponse> {
  const res = await request<TokenResponse>("/auth/register", {
    method: "POST",
    auth: false,
    body: { email, password, full_name: fullName },
  });
  setToken(res.access_token);
  return res;
}

export function logout(): void {
  setToken(null);
}

export function me(): Promise<User> {
  return request<User>("/auth/me");
}
