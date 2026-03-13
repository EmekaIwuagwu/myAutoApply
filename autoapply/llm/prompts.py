JOB_FIT_PROMPT = """You are a career advisor AI. Analyze this job description and the candidate profile below.

JOB TITLE: {job_title}
COMPANY: {company}
JOB DESCRIPTION: {job_description}

CANDIDATE PROFILE:
Name: {name}
Skills: {skills}
Experience: {experience_years} years
Desired Role: {desired_role}

Task:
1. Give a fit score from 0.0 to 1.0 (1.0 = perfect match)
2. List 3 reasons why they are a good fit
3. List 2 potential gaps or concerns
4. Recommend YES or NO to apply

Respond ONLY in this JSON format:
{{
  "fit_score": 0.85,
  "reasons_for": ["reason1", "reason2", "reason3"],
  "concerns": ["concern1", "concern2"],
  "recommendation": "YES",
  "summary": "One sentence summary"
}}"""

COVER_LETTER_PROMPT = """Write a professional, concise cover letter for the following job.
Match the tone to the company culture described. Keep it under 200 words.
Do not use generic filler phrases.

JOB: {job_title} at {company}
JOB DESCRIPTION EXCERPT: {description_excerpt}
CANDIDATE: {name}, {experience_years} years experience in {skills}

Output only the cover letter text, no subject line, no headers."""

RESUME_TAILOR_PROMPT = """You are a resume optimization expert. Given the job description and the candidate's base resume content, suggest specific edits to better match the job requirements.

JOB TITLE: {job_title}
JOB DESCRIPTION: {job_description}
CURRENT RESUME SUMMARY: {resume_summary}

Output a JSON object with:
{{
  "suggested_summary": "...",
  "keywords_to_add": ["kw1", "kw2"],
  "skills_to_highlight": ["skill1", "skill2"]
}}"""

FORM_FIELD_ANALYSIS_PROMPT = """You are a form-filling assistant. Given these form fields from a job application, map the candidate's information to the appropriate fields.

FORM FIELDS:
{form_fields}

CANDIDATE INFO:
{candidate_info}

Return a JSON object mapping field names/labels to values:
{{
  "field_name_or_label": "value_to_fill",
  ...
}}
Only include fields you can confidently fill. Skip fields you don't have data for."""
