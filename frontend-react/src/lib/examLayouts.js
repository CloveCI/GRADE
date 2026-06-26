/** CIE-style answer layouts — mirrors src/autograder/exam_layouts.py */
export const EXAM_REGION_HINTS = {
  'cie-daa': '3,1,2,1',
  'cie-dm': '2,2,1,1,1',
  'cie-compiler': '3,1,1,2',
  ml: '3,1,1,2',
};

/** Raw OCR strip groups merged into each answer key (0-based indices). */
export const EXAM_KEY_REGION_GROUPS = {
  'cie-daa': [[0], [1], [2], [3, 4], [5], [6]],
  'cie-dm': [[0], [1], [2], [3, 4], [5], [6]],
};

function isDataMiningExam(examId) {
  const key = (examId || '').trim().toLowerCase();
  return key.includes('mining') && !key.includes('compiler');
}

export function hintForKeyCount(keyCount) {
  const n = Number(keyCount) || 0;
  if (n === 6) return '3,1,2,1';
  return '';
}

export function hintForExam(examId) {
  if (!examId) return '';
  const key = examId.trim().toLowerCase();
  if (EXAM_REGION_HINTS[key]) return EXAM_REGION_HINTS[key];
  if (isDataMiningExam(key)) return EXAM_REGION_HINTS['cie-dm'];
  if (key.includes('daa') && !key.includes('dm')) return '3,1,2,1';
  if (key === 'ml') return '3,1,1,2';
  if (key.includes('compiler') || key === 'cd' || key === 'comp') return '3,1,1,2';
  return '';
}

export function keyRegionGroups(examId, keyCount = 0) {
  const preset = hintForExam(examId);
  for (const [id, layout] of Object.entries(EXAM_REGION_HINTS)) {
    if (layout === preset && EXAM_KEY_REGION_GROUPS[id]) {
      const groups = EXAM_KEY_REGION_GROUPS[id];
      if (!keyCount || groups.length === keyCount) return groups;
    }
  }
  if (preset === EXAM_REGION_HINTS['cie-dm']) return EXAM_KEY_REGION_GROUPS['cie-dm'];
  if (preset === EXAM_REGION_HINTS['cie-daa']) return EXAM_KEY_REGION_GROUPS['cie-daa'];
  return null;
}

/** Map 0-based raw strip index → 1-based PDF page. */
export function pageForRawRegionIndex(rawIndex, regionsPerPage) {
  if (!regionsPerPage?.length) return 1;
  let remaining = Number(rawIndex) || 0;
  for (let p = 0; p < regionsPerPage.length; p++) {
    const count = Number(regionsPerPage[p]) || 0;
    if (count < 1) continue;
    if (remaining < count) return p + 1;
    remaining -= count;
  }
  return regionsPerPage.length;
}

/** Map 0-based answer-key index → 1-based PDF page (accounts for merged strips). */
export function pageForRegionIndex(regionIndex, regionsPerPage, examId = '', keyCount = 0) {
  if (!regionsPerPage?.length) return 1;
  const groups = keyRegionGroups(examId, keyCount);
  const ri = Number(regionIndex) || 0;
  if (groups?.[ri]?.length) {
    const firstRaw = Math.min(...groups[ri]);
    return pageForRawRegionIndex(firstRaw, regionsPerPage);
  }
  let remaining = ri;
  for (let p = 0; p < regionsPerPage.length; p++) {
    const count = Number(regionsPerPage[p]) || 0;
    if (count < 1) continue;
    if (remaining < count) return p + 1;
    remaining -= count;
  }
  return regionsPerPage.length;
}
