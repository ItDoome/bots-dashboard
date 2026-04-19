import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-ink-50 px-4">
          <div className="w-full max-w-md rounded-2xl border border-ink-200 bg-white p-8 text-center shadow-sm">
            <h1 className="font-display text-2xl font-semibold text-ink-900">
              Oops
            </h1>
            <p className="mt-2 text-sm text-ink-500">
              Что-то пошло не так. Попробуй перезагрузить страницу.
            </p>
            <pre className="mt-4 max-h-40 overflow-auto rounded-lg bg-ink-100 p-3 text-left text-xs text-red-800">
              {this.state.error?.message}
            </pre>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 inline-flex h-10 items-center gap-2 rounded-full bg-ink-900 px-5 text-sm font-medium text-white transition-colors hover:bg-ink-700"
            >
              Перезагрузить
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
