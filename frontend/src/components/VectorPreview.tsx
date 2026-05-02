import { cn } from "@/lib/utils";

/** Tiny sparkbar visualization of a vector for at-a-glance recognition. */
export function VectorPreview({ vector, className }: { vector: number[]; className?: string }) {
  return (
    <div className={cn("flex h-6 items-end gap-px", className)} title={`${vector.length}-D vector`}>
      {vector.map((v, i) => {
        const h = Math.max(2, Math.abs(v) * 100);
        const positive = v >= 0;
        return (
          <span
            key={i}
            className={cn(
              "w-1 rounded-sm",
              positive ? "bg-primary/70" : "bg-accent/70",
            )}
            style={{ height: `${h}%` }}
          />
        );
      })}
    </div>
  );
}