interface Props {
  vector?: number[];
  width?: number;
  height?: number;
}

// Compact sparkline-style preview of a vector embedding.
export function VectorPreview({ vector, width = 220, height = 36 }: Props) {
  if (!vector || vector.length === 0) {
    return (
      <div className="text-xs text-muted-foreground">no embedding</div>
    );
  }
  const sample = vector.length > 64 ? vector.filter((_, i) => i % Math.ceil(vector.length / 64) === 0) : vector;
  const min = Math.min(...sample);
  const max = Math.max(...sample);
  const range = max - min || 1;
  const step = width / sample.length;
  return (
    <svg width={width} height={height} className="text-primary">
      {sample.map((v, i) => {
        const h = ((v - min) / range) * (height - 4);
        return (
          <rect
            key={i}
            x={i * step}
            y={height - h}
            width={Math.max(1, step - 1)}
            height={h}
            fill="currentColor"
            opacity={0.7}
          />
        );
      })}
    </svg>
  );
}
