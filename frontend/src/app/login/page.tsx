import type { Metadata } from "next";
import { AuthPanel } from "@/components/auth/AuthPanel";

export const metadata: Metadata = { title: "Sign in — Pathwise" };

export default function LoginPage() {
  return <AuthPanel mode="login" />;
}
