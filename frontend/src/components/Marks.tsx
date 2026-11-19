import type { Origin, TrustLevel, Verdict } from "../types";
import { TRUST_LABEL, VERDICT_LABEL } from "../lib/format";

export function Marks({
  verdict,
  trust,
  origin,
}: {
  verdict: Verdict;
  trust: TrustLevel;
  origin?: Origin;
}) {
  return (
    <ul className="marks">
      <li className={`mark mark-${verdict}`}>{VERDICT_LABEL[verdict]}</li>
      <li className={`mark mark-trust mark-${trust}`}>{TRUST_LABEL[trust]}</li>
      {origin === "seed" ? <li className="mark mark-sample">Sample</li> : null}
    </ul>
  );
}
