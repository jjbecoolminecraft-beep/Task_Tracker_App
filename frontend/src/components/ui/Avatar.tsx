import { clsx } from "clsx";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

// Deterministic muted tint per person — stays in the navy/blue family.
const TINTS = [
  "bg-navy-800",
  "bg-primary",
  "bg-navy-700",
  "bg-primary-600",
  "bg-navy-600",
  "bg-[#3E7CA6]",
];

function tintFor(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return TINTS[h % TINTS.length];
}

export function Avatar({
  name,
  id,
  size = 24,
}: {
  name: string;
  id?: string;
  size?: number;
}) {
  return (
    <span
      className={clsx(
        "inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white",
        tintFor(id ?? name),
      )}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.42) }}
      title={name}
      aria-hidden
    >
      {initials(name)}
    </span>
  );
}

export function UserChip({ name, id }: { name: string; id?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-ink">
      <Avatar name={name} id={id} />
      <span className="truncate">{name}</span>
    </span>
  );
}
