import * as React from "react";
import {cn} from "@/lib/utils";

export function Sheet({children, open}: {children: React.ReactNode; open: boolean}) {
  if (!open) return null;
  return <>{children}</>;
}

export function SheetContent({children, className, side = "left"}: {children: React.ReactNode; className?: string; side?: "left" | "right"}) {
  return (
    <div className="fixed inset-0 z-50 bg-slate-950/45">
      <div
        className={cn(
          "fixed top-0 h-full w-[88vw] max-w-sm overflow-y-auto border-border bg-background p-4 shadow-xl",
          side === "left" ? "left-0 border-r" : "right-0 border-l",
          className
        )}
      >
        {children}
      </div>
    </div>
  );
}
