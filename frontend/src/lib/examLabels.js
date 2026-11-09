const EXAM_TITLES = {
  'cie-daa': 'Design & Analysis of Algorithms',
  'daa1': 'Design & Analysis of Algorithms',
  'cie-dm': 'Data Mining',
  'cie-ml': 'Machine Learning',
  'cie-dism': 'Disaster Mitigation',
  'cie-compiler': 'Compiler Design',
  'cie-crypto': 'Cryptography & Network Security',
};

export function formatExamName(id) {
  if (!id) return '';
  const key = String(id).trim().toLowerCase();
  if (EXAM_TITLES[key]) return EXAM_TITLES[key];
  return String(id)
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
