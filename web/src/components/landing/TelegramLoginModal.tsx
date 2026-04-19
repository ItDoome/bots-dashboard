import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  botUsername: string;
  open: boolean;
  onClose: () => void;
}

/** Telegram Login Widget mounted inside a custom modal.
 *
 *  We can't style the widget itself (it's an iframe), but hosting it in
 *  our modal at least lets the Landing page look consistent.
 *
 *  The widget posts to /api/auth/telegram via the GET redirect flow
 *  (``data-auth-url``) — the backend validates HMAC + auth_date and
 *  302s to /dashboard.
 */
export function TelegramLoginModal({ botUsername, open, onClose }: Props) {
  const mount = useRef<HTMLDivElement | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!open || !mount.current) return;
    setLoaded(false);

    // Clear any previous mount.
    mount.current.innerHTML = "";

    const script = document.createElement("script");
    script.async = true;
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.setAttribute("data-telegram-login", botUsername);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "12");
    script.setAttribute("data-auth-url", "/api/auth/telegram");
    script.setAttribute("data-request-access", "write");
    script.onload = () => setLoaded(true);

    mount.current.appendChild(script);

    return () => {
      // Telegram widget modifies DOM outside React — swallow errors during
      // cleanup to prevent "Node.removeChild: not a child" crashes.
      try {
        if (mount.current) mount.current.innerHTML = "";
      } catch {
        // ignored
      }
    };
  }, [open, botUsername]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/40 px-4 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-ink-200 bg-white p-8 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="font-display text-2xl font-semibold text-ink-900">
              Sign in
            </h2>
            <p className="mt-1 text-sm text-ink-500">
              Авторизация через твой Telegram аккаунт
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1 text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        <div className="mb-4 rounded-xl border border-ink-200 bg-ink-50 p-4 text-xs text-ink-500">
          <p>
            Бот проверит твой Telegram ID по allowlist'у. Если тебя в списке
            нет — доступ будет отклонён.
          </p>
        </div>

        <div
          ref={mount}
          className="flex min-h-[60px] items-center justify-center"
        >
          {!loaded && (
            <div className="text-sm text-ink-500">Загружаю виджет…</div>
          )}
        </div>

        <div className="mt-6 flex justify-end">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Отмена
          </Button>
        </div>
      </div>
    </div>
  );
}
