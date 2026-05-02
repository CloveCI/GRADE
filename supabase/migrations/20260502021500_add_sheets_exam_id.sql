-- Link uploaded sheets to exam IDs for portal filtering / joins.
ALTER TABLE public.sheets
ADD COLUMN IF NOT EXISTS exam_id TEXT;

CREATE INDEX IF NOT EXISTS idx_sheets_exam_created
    ON public.sheets (exam_id, created_at DESC);
