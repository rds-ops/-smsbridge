import * as React from "react";
import {cn} from "@/lib/utils";

export function Separator({className, decorative = true, orientation = "horizontal", ...props}: React.HTMLAttributes<HTMLDivElement> & {
  decorative?: boolean;
  orientation?: "horizontal" | "vertical";
}) {
  return (
    <div
      aria-orientation={orientation}
      role={decorative ? "none" : "separator"}
      className={cn(orientation === "horizontal" ? "h-px w-full" : "h-full w-px", "shrink-0 bg-border", className)}
      {...props}
    />
  );
}
