import * as React from "react";
import {cn} from "@/lib/utils";

export function Dialog({children, open}: {children: React.ReactNode; open: boolean}) {
  if (!open) return null;
  return <>{children}</>;
}

export function DialogContent({children, className}: {children: React.ReactNode; className?: string}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/45 px-4">
      <div className={cn("w-full max-w-md rounded-2xl border border-border bg-background p-5 shadow-xl", className)}>
        {children}
      </div>
    </div>
  );
}

export function DialogHeader({children, className}: {children: React.ReactNode; className?: string}) {
  return <div className={cn("space-y-1.5", className)}>{children}</div>;
}

export function DialogTitle({children, className}: {children: React.ReactNode; className?: string}) {
  return <h2 className={cn("text-xl font-semibold", className)}>{children}</h2>;
}

export function DialogDescription({children, className}: {children: React.ReactNode; className?: string}) {
  return <p className={cn("text-sm leading-6 text-muted-foreground", className)}>{children}</p>;
}
