import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "../../lib/utils";

const variants = cva("inline-flex items-center justify-center rounded-xl px-4 py-3 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 disabled:pointer-events-none disabled:opacity-50", { variants: { variant: { default: "bg-cyan-100 text-slate-950 hover:bg-white", outline: "border border-slate-700 text-slate-200 hover:bg-slate-800" } }, defaultVariants: { variant: "default" } });
type Props = ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof variants> & { asChild?: boolean };
export const Button = forwardRef<HTMLButtonElement, Props>(({ className, variant, asChild, ...props }, ref) => { const Comp = asChild ? Slot : "button"; return <Comp className={cn(variants({ variant }), className)} ref={ref} {...props} />; });
Button.displayName = "Button";
