/** Rubric dimensions — mirrors src/autograder/schemas.py */

export const RUBRIC_SCALE_MAX = 5;

export const RUBRIC_DIMENSIONS = [
  { key: 'factual_accuracy', label: 'Accuracy' },
  { key: 'conceptual_completeness', label: 'Completeness' },
  { key: 'reasoning', label: 'Reasoning' },
  { key: 'domain_terminology', label: 'Terminology' },
  { key: 'length', label: 'Length' },
];

/** Green check when score is at least 60% of scale max. */
export function rubricPointsFromScores(rubricScores) {
  if (!rubricScores) return [];
  const passAt = Math.ceil(RUBRIC_SCALE_MAX * 0.6);
  return RUBRIC_DIMENSIONS.map(({ key, label }) => {
    const score = rubricScores[key] ?? 0;
    return {
      ok: score >= passAt,
      text: `${label} — ${score}/${RUBRIC_SCALE_MAX}`,
    };
  });
}

export function hasManualOverride(flags) {
  return Array.isArray(flags) && flags.map(String).includes('human_override');
}
