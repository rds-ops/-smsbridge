import * as React from "react";
import {cn} from "@/lib/utils";

export function DropdownMenu({children}: {children: React.ReactNode}) {
  return <div className="relative inline-flex">{children}</div>;
}

export function DropdownMenuTrigger({children, ...props}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props}>{children}</button>;
}

export function DropdownMenuContent({children, className}: {children: React.ReactNode; className?: string}) {
  return (
    <div className={cn("absolute right-0 top-full z-50 mt-2 min-w-48 rounded-xl border border-border bg-background p-1 shadow-lg", className)}>
      {children}
    </div>
  );
}

export function DropdownMenuItem({children, className, ...props}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={cn("flex w-full items-center rounded-lg px-3 py-2 text-left text-sm hover:bg-muted", className)} {...props}>
      {children}
    </button>
  );
}
