import { Link } from "react-router-dom";
import { useTitle } from "../lib/title";

export function NotFoundPage() {
  useTitle("Page not found");
  return (
    <div className="wrap board">
      <section className="soon">
        <h1>That page isn't on the board</h1>
        <p>
          <Link className="back-link" to="/">
            Back to the board
          </Link>
        </p>
      </section>
    </div>
  );
}
