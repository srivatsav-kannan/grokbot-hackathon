import type { Origin, TrustLevel, Verdict } from "../types";
import { TRUST_LABEL, VERDICT_LABEL } from "../lib/format";

export function Marks({
  verdict,
  trust,
  origin,
  sourceName,
}: {
  verdict: Verdict;
  trust: TrustLevel;
  origin?: Origin;
  sourceName?: string;
}) {
  const external = origin === "scout" ? `from ${sourceName || "another site"}` : null;
  return (
    <ul className="marks">
      <li className={`mark mark-${verdict}`}>{VERDICT_LABEL[verdict]}</li>
      <li className={`mark mark-trust mark-${trust}`}>{TRUST_LABEL[trust]}</li>
      {origin === "lister" ? <li className="mark mark-native">Fairlot native</li> : null}
      {external ? <li className="mark mark-external">{external}</li> : null}
    </ul>
  );
}
