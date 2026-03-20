import re
import logging
from lingua import LanguageDetectorBuilder

logger = logging.getLogger(__name__)

class TitleLanguageDetector:
    def __init__(self):
        self.detector = LanguageDetectorBuilder.from_all_spoken_languages().build()

    def clean_title(self, title: str) -> str:
        if not title:
            return ""
        clean = re.sub(r'\[.*?\]|\(.*?\)', '', title)
        clean = re.sub(r'(?i)\b(official|music video|lyric video|audio|mv|feat|ft|prod)\b', '', clean)
        clean = re.sub(r'[^\w\s\'-]', ' ', clean)
        return re.sub(r'\s+', ' ', clean).strip()

    def detect(self, title: str) -> str:
        clean_text = self.clean_title(title)
        
        if len(clean_text) < 2:
            return "unknown"

        confidence_values = self.detector.compute_language_confidence_values(clean_text)
        
        if confidence_values:
            top_match = confidence_values[0]
            
            # Keep the logger so you can watch it work!
            top_3_str = ", ".join([f"{cv.language.name} ({cv.value:.2f})" for cv in confidence_values[:3]])
            logger.info(f"🔍 Lingua Analysis for '{clean_text}': {top_3_str}")
            
            # --- THE FIX: Lowered threshold to 0.15 for short song titles ---
            if top_match.value >= 0.15:
                lang_name = top_match.language.iso_code_639_1.name.lower()
                
                if lang_name == "zh":
                    lang_name = "ja"
                    
                logger.info(f"✅ Approved: {lang_name} ({top_match.value:.2f} confidence)")
                return lang_name
            else:
                logger.warning(f"⚠️ Rejected: Top match '{top_match.language.name}' only scored {top_match.value:.2f}. Defaulting to 'unknown'.")
                
        return "unknown"