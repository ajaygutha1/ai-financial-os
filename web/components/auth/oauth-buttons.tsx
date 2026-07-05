"use client";

import { Button } from "@/components/ui/button";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-4" aria-hidden="true">
      <path
        fill="currentColor"
        d="M21.35 11.1h-9.17v2.73h6.51c-.33 3.81-3.5 5.44-6.5 5.44A7.27 7.27 0 1 1 12.06 4.9c1.98 0 3.68.73 4.99 1.94l1.9-1.83C17.11 3.13 14.71 2 12.06 2a10 10 0 1 0 0 20c5 0 9.24-3.64 9.24-10 0-.6-.1-1.17-.2-1.9Z"
      />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-4" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.16-1.11-1.47-1.11-1.47-.9-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.9 1.52 2.34 1.08 2.91.83.09-.65.35-1.08.63-1.33-2.22-.25-4.55-1.11-4.55-4.94 0-1.09.39-1.98 1.03-2.68-.1-.26-.45-1.28.1-2.65 0 0 .84-.27 2.75 1.02a9.4 9.4 0 0 1 5 0c1.91-1.3 2.75-1.02 2.75-1.02.55 1.37.2 2.39.1 2.65.64.7 1.03 1.59 1.03 2.68 0 3.84-2.33 4.68-4.56 4.93.36.31.68.92.68 1.85v2.75c0 .27.18.58.69.48A10 10 0 0 0 12 2Z"
      />
    </svg>
  );
}

export function OAuthButtons() {
  return (
    <div className="grid grid-cols-2 gap-3">
      <Button
        variant="outline"
        render={<a href={`${API_BASE_URL}/api/v1/auth/oauth/google`} />}
      >
        <GoogleIcon />
        Google
      </Button>
      <Button
        variant="outline"
        render={<a href={`${API_BASE_URL}/api/v1/auth/oauth/github`} />}
      >
        <GitHubIcon />
        GitHub
      </Button>
    </div>
  );
}
