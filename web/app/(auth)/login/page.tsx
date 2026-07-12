"use client";

import { useState } from "react";
import { BarChart3, ShieldCheck, Sparkles } from "lucide-react";

import { LoginForm } from "@/components/auth/login-form";
import { RegisterForm } from "@/components/auth/register-form";
import { OAuthButtons } from "@/components/auth/oauth-buttons";
import { LogoMark, Wordmark } from "@/components/brand/logo-mark";
import { Separator } from "@/components/ui/separator";

const HIGHLIGHTS = [
  { icon: BarChart3, text: "Every account, one live picture of your net worth." },
  { icon: Sparkles, text: "Explainable AI insights, never a black box." },
  { icon: ShieldCheck, text: "Full audit trail on every number you see." },
];

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");

  return (
    <div className="flex min-h-svh flex-1">
      <div className="relative hidden w-1/2 flex-col justify-between bg-primary p-12 text-primary-foreground lg:flex">
        <div className="flex items-center gap-2.5">
          <LogoMark className="size-8 bg-primary-foreground text-primary" />
          <Wordmark className="text-primary-foreground" />
        </div>

        <div className="max-w-md">
          <p className="font-heading text-3xl leading-snug">
            Your entire financial life, aggregated into one honest picture.
          </p>
          <ul className="mt-8 space-y-4">
            {HIGHLIGHTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-sm text-primary-foreground/80">
                <Icon className="mt-0.5 size-4 shrink-0" />
                {text}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-primary-foreground/50">
          Not a budgeting app — a financial intelligence platform.
        </p>
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-16">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <LogoMark className="size-7" />
            <Wordmark />
          </div>

          <h1 className="font-heading text-2xl">
            {mode === "login" ? "Sign in" : "Create your account"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {mode === "login"
              ? "Welcome back to your financial command center."
              : "Start aggregating your entire financial picture."}
          </p>

          <div className="mt-6 space-y-6">
            {mode === "login" ? <LoginForm /> : <RegisterForm />}

            <div className="flex items-center gap-3">
              <Separator className="flex-1" />
              <span className="text-xs text-muted-foreground">or continue with</span>
              <Separator className="flex-1" />
            </div>

            <OAuthButtons />

            <button
              type="button"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
              className="w-full text-center text-sm text-muted-foreground hover:text-foreground"
            >
              {mode === "login"
                ? "Don't have an account? Create one"
                : "Already have an account? Sign in"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
