import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-ink-50 text-center">
      <div className="font-display text-6xl font-semibold text-ink-900">404</div>
      <p className="mt-3 text-ink-500">Такой страницы нет</p>
      <Link
        to="/dashboard"
        className="mt-6 rounded-full bg-ink-900 px-5 py-2 text-sm font-medium text-white hover:bg-ink-700"
      >
        К дашборду
      </Link>
    </div>
  );
}
