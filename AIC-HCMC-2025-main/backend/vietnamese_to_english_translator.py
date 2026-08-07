from deep_translator import GoogleTranslator

class VietnameseToEnglishTranslator:
    def __init__(self):
        # Initialize Google Translator (online service)
        print(f"[INFO] Initializing Google Translator (requires internet connection)...")
        try:
            self.translator = GoogleTranslator(source='vi', target='en')
            print(f"[INFO] Google Translator initialized successfully.")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Google Translator: {str(e)}")

    def translate(self, vietnamese_query_text):
        if not vietnamese_query_text:
            raise ValueError("vietnamese_query_text must be a non-empty string")
        
        return self.translator.translate(vietnamese_query_text)
