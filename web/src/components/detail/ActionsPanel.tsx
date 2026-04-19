import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ActionButton } from "./ActionButton";
import type { ActionDescriptor } from "@/api/types";

interface ActionsPanelProps {
  slug: string;
  actions: ActionDescriptor[];
}

export function ActionsPanel({ slug, actions }: ActionsPanelProps) {
  if (actions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Действия</CardTitle>
          <CardDescription>Этот бот не экспонирует действий</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Действия</CardTitle>
          <CardDescription>
            Каждое действие записывается в audit log. Двойной клик даст 409 Conflict
            (защита от параллельного запуска).
          </CardDescription>
        </CardHeader>
      </Card>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {actions.map((a) => (
          <ActionButton key={a.key} slug={slug} descriptor={a} />
        ))}
      </div>
    </div>
  );
}
