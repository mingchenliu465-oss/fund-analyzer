import * as React from "react";

const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={`flex h-11 w-full rounded-md border border-border bg-background px-3 py-2 text-base transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:border-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm ${className ?? ""}`}
      ref={ref}
      {...props}
    />
  );
});
Input.displayName = "Input";

export { Input };
