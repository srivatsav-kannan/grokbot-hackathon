import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getNotifications, markNotificationsRead } from "../api/client";
import { useAuth } from "../auth";
import { formatStamp } from "../lib/format";
import type { NotificationItem } from "../types";

export function NotificationBell() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [items, setItems] = useState<NotificationItem[]>([]);

  useEffect(() => {
    if (!user) {
      setUnread(0);
      setItems([]);
      return;
    }
    let stop = false;
    const load = () => {
      getNotifications()
        .then((payload) => {
          if (stop) return;
          setUnread(payload.unread);
          setItems(payload.notifications);
        })
        .catch(() => {
          if (!stop) setUnread(0);
        });
    };
    load();
    const timer = window.setInterval(load, 20000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [user]);

  if (!user) return null;

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && unread > 0) {
      try {
        const payload = await markNotificationsRead();
        setUnread(payload.unread);
        setItems(payload.notifications);
      } catch {
        /* The list still shows the last fetch. */
      }
    }
  }

  return (
    <div className="bell">
      <button type="button" aria-expanded={open} aria-label="Notifications" onClick={() => void toggle()}>
        Alerts
        {unread > 0 ? <span className="bell-count">{unread}</span> : null}
      </button>
      {open ? (
        <div className="bell-panel" role="region" aria-label="Notifications">
          {items.length === 0 ? (
            <p>No alerts yet.</p>
          ) : (
            <ul>
              {items.map((item) => (
                <li key={item.id} data-unread={item.unread ? "true" : "false"}>
                  {item.href ? <Link to={item.href}>{item.message}</Link> : <span>{item.message}</span>}
                  <time dateTime={item.at}>{formatStamp(item.at)}</time>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
