import type { ModelInfo } from "../types";

export default function ModelSelector({
  models,
  value,
  onChange,
  disabled,
}: {
  models: ModelInfo[];
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
}) {
  const byProvider = models.reduce<Record<string, ModelInfo[]>>((acc, m) => {
    (acc[m.provider] ??= []).push(m);
    return acc;
  }, {});

  return (
    <select
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-200 disabled:opacity-50"
    >
      {Object.entries(byProvider).map(([provider, ms]) => (
        <optgroup key={provider} label={provider}>
          {ms.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
