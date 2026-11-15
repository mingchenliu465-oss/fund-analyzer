import * as React from "react";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline" | "ghost";
  size?: "default" | "sm" | "lg" | "icon";
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    const variants = {
      default: "bg-accent text-accent-foreground hover:bg-accent-hover",
      outline: "border border-border bg-background hover:bg-muted",
      ghost: "hover:bg-muted",
    };

    const sizes = {
      default: "min-h-11 px-4 py-2",
      sm: "min-h-11 px-3 text-xs",
      lg: "min-h-12 px-6 text-base",
      icon: "h-11 w-11",
    };

    return (
      <button
        className={`inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className ?? ""}`}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button };
