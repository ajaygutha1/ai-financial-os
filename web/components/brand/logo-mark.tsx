import { cn } from "@/lib/utils";

export function LogoMark({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex items-center justify-center rounded-lg bg-primary text-primary-foreground",
        className
      )}
      aria-hidden="true"
    >
      <svg viewBox="0 0 16 16" className="h-[55%] w-[55%]" fill="none">
        <path
          d="M2 12.5V9.5M8 12.5V6M14 12.5V3"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("font-heading text-lg font-medium tracking-tight", className)}>
      AI Financial OS
    </span>
  );
}
