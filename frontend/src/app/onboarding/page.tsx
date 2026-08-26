import type { Metadata } from "next";
import { Suspense } from "react";
import { Onboarding } from "@/components/onboarding/Onboarding";

export const metadata: Metadata = { title: "Set your goal — Pathwise" };

export default function OnboardingPage() {
  // Onboarding reads `?mode=` to pick its opening branch, so it must sit under
  // a Suspense boundary or the route cannot be prerendered.
  return (
    <Suspense fallback={null}>
      <Onboarding />
    </Suspense>
  );
}
