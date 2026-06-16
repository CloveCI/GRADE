/** OCR read-confidence color for evaluator UI. */
export function confColor(percent) {
  return percent >= 90 ? '#22c55e' : percent >= 75 ? '#f97316' : '#ef4444';
}
