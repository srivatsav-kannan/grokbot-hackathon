import { useLayoutEffect, useRef } from "react";
import { animate } from "motion";
import { formatUsd } from "../lib/format";
import { useReducedMotion } from "../lib/scroll";

export function Price({
  amount,
  className = "price",
  count = false,
  delay = 0,
}: {
  amount: number;
  className?: string;
  count?: boolean;
  delay?: number;
}) {
  const visual = useRef<HTMLSpanElement>(null);
  const reduced = useReducedMotion();
  const label = formatUsd(amount);

  useLayoutEffect(() => {
    const node = visual.current;
    if (!node) return;
    node.textContent = label;
    if (!count || reduced) return;

    const rect = node.getBoundingClientRect();
    const inView = rect.top < window.innerHeight * 0.92 && rect.bottom > 0;
    if (!inView) return;

    const animation = animate(0, amount, {
      duration: 0.7,
      delay,
      ease: "easeOut",
      onUpdate: (value) => {
        node.textContent = formatUsd(Math.round(value));
      },
    });
    return () => animation.stop();
  }, [amount, count, delay, label, reduced]);

  return (
    <span className={className}>
      <span className="sr-only">{label}</span>
      <span ref={visual} aria-hidden="true">
        {label}
      </span>
    </span>
  );
}
