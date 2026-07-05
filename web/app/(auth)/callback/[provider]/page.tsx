"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { refreshAccessToken } from "@/lib/api-client";

export default function OAuthCallbackPage() {
  const router = useRouter();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // The backend already set the refresh cookie via redirect; exchange it
    // for an access token the same way a normal page-reload session restore
    // would, then move on to the dashboard.
    void refreshAccessToken().then((token) => {
      if (cancelled) return;
      if (token) {
        router.replace("/dashboard");
      } else {
        setFailed(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (failed) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 px-4 py-16 text-center">
        <p className="text-sm text-muted-foreground">
          We couldn&apos;t complete sign-in. Please try again.
        </p>
        <button
          type="button"
          onClick={() => router.replace("/login")}
          className="text-sm font-medium underline underline-offset-4"
        >
          Back to sign in
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-1 items-center justify-center px-4 py-16">
      <p className="text-sm text-muted-foreground">Finishing sign-in...</p>
    </div>
  );
}
