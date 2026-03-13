import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)


def parse_resume(file_path: str) -> Dict:
    """Parse a resume file (PDF or DOCX) and return extracted text and metadata."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Resume file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _parse_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return _parse_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _parse_pdf(file_path: str) -> Dict:
    """Parse a PDF resume using pdfplumber."""
    try:
        import pdfplumber

        full_text = ""
        pages_text = []

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages_text.append(text)
                full_text += text + "\n"

        return {
            "full_text": full_text.strip(),
            "pages": pages_text,
            "file_type": "pdf",
            "summary": _extract_summary(full_text),
            "skills": _extract_skills(full_text),
        }
    except ImportError:
        logger.error("pdfplumber not installed")
        return {"full_text": "", "pages": [], "file_type": "pdf", "summary": "", "skills": ""}
    except Exception as e:
        logger.error(f"PDF parse error: {e}")
        return {"full_text": "", "pages": [], "file_type": "pdf", "summary": "", "skills": ""}


def _parse_docx(file_path: str) -> Dict:
    """Parse a DOCX resume using python-docx."""
    try:
        from docx import Document

        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n".join(paragraphs)

        return {
            "full_text": full_text.strip(),
            "pages": [full_text],
            "file_type": "docx",
            "summary": _extract_summary(full_text),
            "skills": _extract_skills(full_text),
        }
    except ImportError:
        logger.error("python-docx not installed")
        return {"full_text": "", "pages": [], "file_type": "docx", "summary": "", "skills": ""}
    except Exception as e:
        logger.error(f"DOCX parse error: {e}")
        return {"full_text": "", "pages": [], "file_type": "docx", "summary": "", "skills": ""}


def _extract_summary(text: str) -> str:
    """Extract the first paragraph/summary section from resume text."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    # Look for a summary section
    summary_keywords = ["summary", "objective", "profile", "about"]
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in summary_keywords):
            # Return next few lines as summary
            return " ".join(lines[i + 1:i + 5])
    # Fallback: return first 3 meaningful lines
    return " ".join(lines[:3])


def _extract_skills(text: str) -> str:
    """Extract skills section from resume text."""
    lines = text.split("\n")
    skill_keywords = ["skills", "technologies", "tools", "expertise", "competencies"]
    in_skills = False
    skills_lines = []

    for line in lines:
        line = line.strip()
        if any(kw in line.lower() for kw in skill_keywords):
            in_skills = True
            continue
        if in_skills:
            if not line or any(
                kw in line.lower()
                for kw in ["experience", "education", "projects", "work history"]
            ):
                break
            skills_lines.append(line)

    return ", ".join(skills_lines) if skills_lines else ""
