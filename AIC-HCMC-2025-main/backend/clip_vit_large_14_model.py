"""
Drop-in replacement for backend/clip_vit_large_14_model.py.

Changes vs. the original:
1. Uses `CLIPModel` / `CLIPProcessor` instead of `AutoModelForZeroShotImageClassification`.
   On transformers v5.x, `get_image_features()` / `get_text_features()` on the Auto* wrapper
   can come back as `BaseModelOutputWithPooling` instead of a plain tensor — this class
   normalizes that away in `_to_vector()` regardless of which shape you get, so it keeps
   working across transformers versions.
2. Adds `embed_images()` for batched image -> vector encoding (needed by TRAKE dense
   stage-2 refinement, which scores many candidate frames against one text query).
3. Both `embed()` and `embed_images()` now L2-normalize their output, matching how the
   offline pipeline stores clip_feature_vector / scene_feature_vector (see
   data_processing/main.py), so raw dot products between query and stored vectors are
   directly comparable without callers having to re-normalize.

Existing call sites (`clip14_model.embed(text)`) keep working unchanged.
"""

from typing import List, Union

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

MODEL_NAME = "openai/clip-vit-large-patch14-336"


def _to_vector(output) -> torch.Tensor:
    """Normalize the various shapes transformers has returned across versions for
    get_image_features()/get_text_features() into a plain (batch, dim) tensor."""
    if torch.is_tensor(output):
        return output
    for attr in ("image_embeds", "text_embeds", "pooler_output"):
        val = getattr(output, attr, None)
        if val is not None:
            return val
    raise TypeError(f"Unrecognized CLIP output type from transformers: {type(output)}")


class CLIP_ViT_L_14:
    def __init__(self):
        if torch.backends.mps.is_available():
            self.device = "mps"
        elif torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"
        print(f"[INFO] Using device: {self.device}")

        print(f"[INFO] Model {MODEL_NAME} is loading...")
        try:
            self.processor = CLIPProcessor.from_pretrained(MODEL_NAME)
            self.model = CLIPModel.from_pretrained(MODEL_NAME)
            self.model.to(self.device)
            self.model.eval()
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {str(e)}")

        print(f"[INFO] Model loaded successfully.")

    def embed(self, query_text: str) -> np.ndarray:
        """Encode a single text query -> L2-normalized (768,) vector."""
        inputs = self.processor(text=query_text, return_tensors="pt", padding=True, truncation=True)
        inputs = inputs.to(self.device)
        with torch.no_grad():
            text_embeddings = _to_vector(self.model.get_text_features(**inputs))
            text_embeddings = text_embeddings / text_embeddings.norm(p=2, dim=-1, keepdim=True)
        return text_embeddings.cpu().numpy().squeeze()

    def embed_images(self, images: Union[Image.Image, List[Image.Image]], batch_size: int = 32) -> np.ndarray:
        """
        Encode one or many PIL images -> L2-normalized (N, 768) vectors (or (768,) for
        a single image). Used by TRAKE dense stage-2 refinement to score every frame in
        a re-sampled window against a sub-event query in one pass.
        """
        single = isinstance(images, Image.Image)
        image_list = [images] if single else list(images)

        all_vecs = []
        with torch.no_grad():
            for i in range(0, len(image_list), batch_size):
                chunk = image_list[i : i + batch_size]
                inputs = self.processor(images=chunk, return_tensors="pt")
                inputs = inputs.to(self.device)
                image_embeddings = _to_vector(self.model.get_image_features(**inputs))
                image_embeddings = image_embeddings / image_embeddings.norm(p=2, dim=-1, keepdim=True)
                all_vecs.append(image_embeddings.cpu().numpy())

        result = np.concatenate(all_vecs, axis=0)
        return result[0] if single else result