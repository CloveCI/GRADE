/** CIE-style answer layouts — mirrors src/autograder/exam_layouts.py */
export const EXAM_REGION_HINTS = {
  'cie-daa': '3,1,2,1',
  'cie-dm': '2,2,1,1,1',
  'cie-compiler': '3,1,1,2',
  ml: '3,1,1,2',
};

export function hintForKeyCount(keyCount) {
  const n = Number(keyCount) || 0;
  if (n === 6) return '3,1,2,1';
  return '';
}

export function hintForExam(examId) {
  if (!examId) return '';
  const key = examId.trim().toLowerCase();
  if (EXAM_REGION_HINTS[key]) return EXAM_REGION_HINTS[key];
  if (key.includes('daa') && !key.includes('dm')) return '3,1,2,1';
  if (key === 'ml') return '3,1,1,2';
  if (key.includes('compiler') || key === 'cd' || key === 'comp') return '3,1,1,2';
  return '';
}

/** Map 0-based region index → 1-based PDF page (e.g. layout [3,1,1,1]). */
export function pageForRegionIndex(regionIndex, regionsPerPage) {
  if (!regionsPerPage?.length) return 1;
  let remaining = Number(regionIndex) || 0;
  for (let p = 0; p < regionsPerPage.length; p++) {
    const count = Number(regionsPerPage[p]) || 0;
    if (count < 1) continue;
    if (remaining < count) return p + 1;
    remaining -= count;
  }
  return regionsPerPage.length;
}
