import { formatUsd } from "../lib/format";

export function Price({ amount, className = "price" }: { amount: number; className?: string }) {
  return <span className={className}>{formatUsd(amount)}</span>;
}
