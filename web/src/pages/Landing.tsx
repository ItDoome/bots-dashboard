import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Bot, Gauge, ShieldCheck, Activity, LayoutDashboard, Fish } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HeroMock } from "@/components/landing/HeroMock";
import { TelegramLoginModal } from "@/components/landing/TelegramLoginModal";
import { useMe } from "@/api/hooks";

const TG_BOT_USERNAME =
  (typeof import.meta !== "undefined" &&
    (import.meta as unknown as { env?: { VITE_TG_BOT_USERNAME?: string } }).env
      ?.VITE_TG_BOT_USERNAME) ||
  "lolsZauto_bot";

export default function Landing() {
  const [modalOpen, setModalOpen] = useState(false);
  const { data: me } = useMe();
  const loggedIn = Boolean(me?.tg_id);

  return (
    <div className="min-h-screen bg-ink-50 text-ink-900">
      {/* Dark top nav */}
      <header className="bg-ink-950 text-ink-100">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2 font-display text-lg font-semibold">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-white text-ink-950">
              <Bot size={16} />
            </span>
            doomedash
          </div>
          <nav className="hidden items-center gap-6 text-sm text-ink-100/80 md:flex">
            <a href="#features" className="hover:text-white">
              Features
            </a>
            <a href="#projects" className="hover:text-white">
              Projects
            </a>
            <a href="/voodoo/" target="_blank" rel="noreferrer" className="hover:text-white">
              Voodoo
            </a>
          </nav>
          {loggedIn ? (
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-1.5 text-sm font-medium text-ink-950 transition-colors hover:bg-ink-200"
            >
              <LayoutDashboard size={14} />
              {me?.first_name ?? me?.username ?? "Dashboard"}
            </Link>
          ) : (
            <button
              onClick={() => setModalOpen(true)}
              className="rounded-full bg-white px-4 py-1.5 text-sm font-medium text-ink-950 transition-colors hover:bg-ink-200"
            >
              Sign in
            </button>
          )}
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 dotted-bg pointer-events-none" />
        <div className="relative mx-auto max-w-5xl px-6 pt-24 pb-16 text-center">
          <h1 className="font-display text-5xl font-semibold leading-[1.05] tracking-tight md:text-6xl">
            The only bot control center
            <br />
            <span className="text-ink-500">built for your team</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-ink-500">
            Единая панель для мониторинга и управления всеми твоими Telegram
            ботами. Статусы, метрики, логи, настройки, действия — всё в одном
            месте, с авторизацией через Telegram.
          </p>

          <div className="mt-10 flex items-center justify-center gap-3">
            {loggedIn ? (
              <Link
                to="/dashboard"
                className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-ink-900 px-6 text-base font-medium text-white transition-colors hover:bg-ink-700"
              >
                <LayoutDashboard size={16} />
                Открыть дашборд
              </Link>
            ) : (
              <Button size="lg" onClick={() => setModalOpen(true)}>
                Get started
                <ArrowRight size={16} />
              </Button>
            )}
            <a
              href="#features"
              className="inline-flex h-12 items-center justify-center rounded-full border border-ink-200 bg-white px-6 text-sm font-medium text-ink-900 transition-colors hover:bg-ink-100"
            >
              Learn more
            </a>
          </div>

          <HeroMock />
        </div>
      </section>

      {/* Features */}
      <section id="features" className="mx-auto max-w-6xl px-6 py-24">
        <h2 className="font-display text-3xl font-semibold text-ink-900">
          Что внутри
        </h2>
        <p className="mt-2 max-w-2xl text-ink-500">
          Архитектура спроектирована под несколько серверов и бесконечное
          количество ботов. Добавить нового — один файл-адаптер.
        </p>

        <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          <FeatureCard
            icon={<Bot size={20} />}
            title="Multi-bot"
            body="Каждый бот — отдельный плагин со своими метриками, настройками и действиями. Добавление нового бота = 2 файла."
          />
          <FeatureCard
            icon={<Gauge size={20} />}
            title="Live metrics"
            body="Статус сервисов, ключевые KPI, 24h velocity, rate limits. Обновление каждые 10–15 секунд, паузы при свёрнутой вкладке."
          />
          <FeatureCard
            icon={<ShieldCheck size={20} />}
            title="Safe by default"
            body="Авторизация через Telegram, CSRF defense, audit log с редактированием секретов, dedicated пользователи + sudoers whitelist."
          />
          <FeatureCard
            icon={<Activity size={20} />}
            title="Graceful degradation"
            body="Агент упал? Панель покажет warning на карточке, остальные боты работают. Cold start подхватывает последний успешный кэш."
          />
        </div>
      </section>

      {/* Projects */}
      <section id="projects" className="border-t border-ink-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-24">
          <h2 className="font-display text-3xl font-semibold text-ink-900">
            Проекты
          </h2>
          <p className="mt-2 max-w-2xl text-ink-500">
            Статические веб-приложения, которые живут на этом же домене. Открываются в новой вкладке.
          </p>

          <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            <ProjectCard
              icon={<Fish size={20} />}
              href="/voodoo/"
              title="Voodoo Fishin'"
              body="Интерактивная карта + fishing guide + bestiary для игры Voodoo Fishin'. Слои, зоны, маркеры рыбы."
            />
          </div>
        </div>
      </section>

      <footer className="border-t border-ink-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6 text-xs text-ink-500">
          <div>© {new Date().getFullYear()} doomedash</div>
          <div>Built with FastAPI · React · Tailwind</div>
        </div>
      </footer>

      <TelegramLoginModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        botUsername={TG_BOT_USERNAME}
      />
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-2xl border border-ink-200 bg-white p-6">
      <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-ink-100 text-ink-700">
        {icon}
      </div>
      <h3 className="mt-4 font-semibold text-ink-900">{title}</h3>
      <p className="mt-2 text-sm text-ink-500">{body}</p>
    </div>
  );
}

function ProjectCard({
  icon,
  href,
  title,
  body,
}: {
  icon: React.ReactNode;
  href: string;
  title: string;
  body: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="group block rounded-2xl border border-ink-200 bg-white p-6 transition-all hover:border-ink-900 hover:shadow-lg"
    >
      <div className="flex items-start justify-between">
        <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-ink-100 text-ink-700 group-hover:bg-ink-900 group-hover:text-white">
          {icon}
        </div>
        <ArrowRight
          size={18}
          className="text-ink-400 transition-transform group-hover:translate-x-1 group-hover:text-ink-900"
        />
      </div>
      <h3 className="mt-4 font-semibold text-ink-900">{title}</h3>
      <p className="mt-2 text-sm text-ink-500">{body}</p>
    </a>
  );
}
