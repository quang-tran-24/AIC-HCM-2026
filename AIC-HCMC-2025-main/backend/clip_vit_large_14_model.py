from transformers import CLIPProcessor, CLIPModel
import torch

class CLIP_ViT_L_14:
    def __init__(self):
        if torch.backends.mps.is_available():
            self.device = "mps"
        elif torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"
        print(f"[INFO] Using device: {self.device}")

        print(f"[INFO] Model openai/clip-vit-large-patch14 is loading...")
        try:
            self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14-336")
            self.model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14-336")
            self.model.to(self.device)
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {str(e)}")

        print(f"[INFO] Model loaded successfully.")

    def embed(self, query_text):
        inputs = self.processor(text=query_text, return_tensors="pt", padding=True, truncation=True)
        inputs.to(self.device)
        with torch.no_grad():
            outputs = self.model.get_text_features(**inputs)
            text_embeddings = outputs.pooler_output  # transformers v5.x: embedding nằm ở đây

        text_embedding = text_embeddings.cpu().numpy().squeeze()
        return text_embedding