import * as React from "react";
import {cn} from "@/lib/utils";

export function Tabs({children, className}: {children: React.ReactNode; className?: string}) {
  return <div className={cn("grid gap-3", className)}>{children}</div>;
}

export function TabsList({children, className}: {children: React.ReactNode; className?: string}) {
  return <div className={cn("inline-flex rounded-xl bg-muted p-1", className)}>{children}</div>;
}

export function TabsTrigger({active, children, className, ...props}: React.ButtonHTMLAttributes<HTMLButtonElement> & {active?: boolean}) {
  return (
    <button
      className={cn("rounded-lg px-3 py-2 text-sm font-medium transition", active ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground", className)}
      {...props}
    >
      {children}
    </button>
  );
}

export function TabsContent({children, className}: {children: React.ReactNode; className?: string}) {
  return <div className={cn("outline-none", className)}>{children}</div>;
}
