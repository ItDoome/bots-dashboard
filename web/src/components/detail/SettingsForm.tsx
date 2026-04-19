import { useEffect, useMemo, useState } from "react";
import { Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Switch } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useUpdateSettings } from "@/api/hooks";
import type {
  SettingField,
  SettingsResponse,
  SettingsSection,
} from "@/api/types";

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────

type FormState = Record<string, unknown>;

function coerce(field: SettingField, raw: unknown): unknown {
  if (raw === "" || raw == null) return null;
  switch (field.type) {
    case "integer": {
      const n = Number.parseInt(String(raw), 10);
      return Number.isFinite(n) ? n : null;
    }
    case "number": {
      const n = Number.parseFloat(String(raw));
      return Number.isFinite(n) ? n : null;
    }
    case "boolean":
      return Boolean(raw);
    case "json":
      try {
        return JSON.parse(String(raw));
      } catch {
        return raw;
      }
    default:
      return String(raw);
  }
}

function validate(field: SettingField, value: unknown): string | null {
  if (
    field.required &&
    (value === null || value === undefined || value === "")
  ) {
    return "Обязательное поле";
  }
  if (value === null || value === undefined || value === "") return null;
  if (field.type === "integer" || field.type === "number") {
    const n = Number(value);
    if (!Number.isFinite(n)) return "Не число";
    if (field.minimum != null && n < field.minimum)
      return `Минимум ${field.minimum}`;
    if (field.maximum != null && n > field.maximum)
      return `Максимум ${field.maximum}`;
  }
  if (field.enum_values && !field.enum_values.includes(String(value))) {
    return `Должно быть одно из: ${field.enum_values.join(", ")}`;
  }
  return null;
}

function equalish(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (a == null && b == null) return true;
  if (typeof a === "number" || typeof b === "number") {
    return Number(a) === Number(b);
  }
  if (typeof a === "boolean" || typeof b === "boolean") {
    return Boolean(a) === Boolean(b);
  }
  return String(a ?? "") === String(b ?? "");
}

// ─────────────────────────────────────────────────────────────
// Field renderer
// ─────────────────────────────────────────────────────────────

interface FieldRendererProps {
  field: SettingField;
  value: unknown;
  onChange: (v: unknown) => void;
  error: string | null;
}

function FieldRenderer({ field, value, onChange, error }: FieldRendererProps) {
  const id = `field-${field.path}`;
  const errorEl = error ? (
    <span className="mt-1 text-xs text-red-700">{error}</span>
  ) : null;

  if (field.type === "boolean") {
    return (
      <div className="flex items-start justify-between gap-4 py-3 border-b border-ink-100 last:border-0">
        <div className="flex-1">
          <label htmlFor={id} className="block text-sm font-medium text-ink-900">
            {field.label}
          </label>
          {field.help && (
            <span className="mt-0.5 block text-xs text-ink-500">{field.help}</span>
          )}
          {errorEl}
        </div>
        <Switch
          checked={Boolean(value)}
          onCheckedChange={(v) => onChange(v)}
        />
      </div>
    );
  }

  if (field.type === "enum" && field.enum_values) {
    return (
      <div className="flex flex-col py-3 border-b border-ink-100 last:border-0">
        <label htmlFor={id} className="text-sm font-medium text-ink-900">
          {field.label}
        </label>
        {field.help && (
          <span className="mt-0.5 text-xs text-ink-500">{field.help}</span>
        )}
        <select
          id={id}
          value={value == null ? "" : String(value)}
          onChange={(e) => onChange(e.target.value)}
          className="mt-2 h-10 rounded-lg border border-ink-200 bg-white px-3 text-sm text-ink-900 focus:border-ink-900 focus:outline-none focus:ring-1 focus:ring-ink-900"
        >
          <option value="">—</option>
          {field.enum_values.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        {errorEl}
      </div>
    );
  }

  const inputType =
    field.type === "integer" || field.type === "number" ? "number" : "text";

  return (
    <div className="flex flex-col py-3 border-b border-ink-100 last:border-0">
      <label htmlFor={id} className="text-sm font-medium text-ink-900">
        {field.label}
      </label>
      {field.help && (
        <span className="mt-0.5 text-xs text-ink-500">{field.help}</span>
      )}
      <Input
        id={id}
        type={inputType}
        value={value == null ? "" : String(value)}
        onChange={(e) => onChange(e.target.value)}
        min={field.minimum ?? undefined}
        max={field.maximum ?? undefined}
        className="mt-2"
      />
      {errorEl}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Main form
// ─────────────────────────────────────────────────────────────

interface SettingsFormProps {
  slug: string;
  data: SettingsResponse;
}

export function SettingsForm({ slug, data }: SettingsFormProps) {
  const [form, setForm] = useState<FormState>({});
  const [initial, setInitial] = useState<FormState>({});
  const [errors, setErrors] = useState<Record<string, string | null>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const mutation = useUpdateSettings(slug);

  const sections: SettingsSection[] = data.schema.sections ?? [];

  // Reset the form whenever fresh schema/values arrive.
  useEffect(() => {
    const values: FormState = {};
    for (const section of sections) {
      for (const field of section.fields) {
        values[field.path] =
          data.values.values[field.path] ?? field.default ?? null;
      }
    }
    setForm(values);
    setInitial(values);
    setErrors({});
  }, [data, sections]);

  const dirtyKeys = useMemo(() => {
    const out: string[] = [];
    for (const k of Object.keys(form)) {
      if (!equalish(form[k], initial[k])) out.push(k);
    }
    return out;
  }, [form, initial]);

  const handleChange = (field: SettingField, raw: unknown) => {
    const value = coerce(field, raw);
    setForm((prev) => ({ ...prev, [field.path]: value }));
    setErrors((prev) => ({ ...prev, [field.path]: validate(field, value) }));
    setOkMsg(null);
  };

  const handleSave = async () => {
    setServerError(null);
    setOkMsg(null);

    // Validate all fields before sending
    const allErrors: Record<string, string | null> = {};
    let hasError = false;
    for (const section of sections) {
      for (const field of section.fields) {
        const err = validate(field, form[field.path]);
        allErrors[field.path] = err;
        if (err) hasError = true;
      }
    }
    setErrors(allErrors);
    if (hasError) return;

    const patch: Record<string, unknown> = {};
    for (const k of dirtyKeys) patch[k] = form[k];
    if (Object.keys(patch).length === 0) {
      setOkMsg("Нет изменений");
      return;
    }

    try {
      await mutation.mutateAsync(patch);
      setInitial({ ...form });
      setOkMsg(`Сохранено: ${dirtyKeys.length} полей`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setServerError(msg);
    }
  };

  if (sections.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6 text-sm text-ink-500">
          Этот бот не экспонирует редактируемых настроек.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {sections.map((section) => (
        <Card key={section.title}>
          <CardHeader>
            <CardTitle>{section.title}</CardTitle>
            {section.description && (
              <CardDescription>{section.description}</CardDescription>
            )}
          </CardHeader>
          <CardContent className="pt-0">
            <div className="flex flex-col">
              {section.fields.map((field) => (
                <FieldRenderer
                  key={field.path}
                  field={field}
                  value={form[field.path]}
                  onChange={(v) => handleChange(field, v)}
                  error={errors[field.path] ?? null}
                />
              ))}
            </div>
          </CardContent>
        </Card>
      ))}

      <div className="flex items-center justify-between gap-4 rounded-2xl border border-ink-200 bg-white p-4 shadow-sm">
        <div className="text-sm">
          {serverError ? (
            <span className="text-red-700">Ошибка: {serverError}</span>
          ) : okMsg ? (
            <span className="text-emerald-700">{okMsg}</span>
          ) : dirtyKeys.length > 0 ? (
            <span className="text-ink-500">
              Изменено полей: {dirtyKeys.length}
            </span>
          ) : (
            <span className="text-ink-500">Нет изменений</span>
          )}
        </div>
        <Button
          onClick={handleSave}
          disabled={mutation.isPending || dirtyKeys.length === 0}
          size="md"
        >
          <Save size={14} />
          {mutation.isPending ? "Сохраняю…" : "Сохранить"}
        </Button>
      </div>
    </div>
  );
}
