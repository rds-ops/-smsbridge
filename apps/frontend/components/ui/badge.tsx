import * as React from "react";
import {cn} from "@/lib/utils";

type BadgeVariant = "default" | "secondary" | "outline" | "destructive";

const variants: Record<BadgeVariant, string> = {
  default: "border-transparent bg-primary text-primary-foreground",
  secondary: "border-transparent bg-muted text-foreground",
  outline: "border-border text-foreground",
  destructive: "border-transparent bg-destructive text-destructive-foreground"
};

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: BadgeVariant;
}

export function Badge({className, variant = "default", ...props}: BadgeProps) {
  return (
    <div
      className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition", variants[variant], className)}
      {...props}
    />
  );
}
