import type { Metadata } from "next";
import { Onboarding } from "@/components/onboarding/Onboarding";

export const metadata: Metadata = { title: "Set your goal — Pathwise" };

export default function OnboardingPage() {
  return <Onboarding />;
}
