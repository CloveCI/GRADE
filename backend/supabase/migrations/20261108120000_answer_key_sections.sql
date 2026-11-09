-- Exam sections with a choice ("PART B: answer any 2 of 3"): the section a key belongs to and how many of its
-- questions count towards the total. NULL section_pick means every question counts. Mirrors db.py init_db().
ALTER TABLE public.answer_keys ADD COLUMN IF NOT EXISTS section TEXT;
ALTER TABLE public.answer_keys ADD COLUMN IF NOT EXISTS section_pick INTEGER;
