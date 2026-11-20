import { useEffect, useState } from "react";
import { getActivity } from "../api/client";
import { formatStamp } from "../lib/format";

type Event = { at: string; message: string };

export function ActivityPanel() {
  const [events, setEvents] = useState<Event[]>([]);

  useEffect(() => {
    let stop = false;
    const load = () => {
      getActivity()
        .then((payload) => {
          if (!stop) setEvents(payload.events.slice(0, 6));
        })
        .catch(() => {
          if (!stop) setEvents([]);
        });
    };
    load();
    const timer = window.setInterval(load, 15000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <section className="activity" aria-live="polite" aria-labelledby="activity-heading">
      <h2 id="activity-heading">Agents at work</h2>
      {events.length === 0 ? (
        <p>Scout, the inspector, and the buyer bots will report here.</p>
      ) : (
        <ul>
          {events.map((event) => (
            <li key={`${event.at}-${event.message}`}>
              <time dateTime={event.at}>{formatStamp(event.at)}</time>
              <span>{event.message}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
