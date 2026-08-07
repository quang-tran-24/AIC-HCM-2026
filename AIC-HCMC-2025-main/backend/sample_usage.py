from clip_vit_large_14_model import CLIP_ViT_L_14
from vietnamese_to_english_translator import VietnameseToEnglishTranslator


clip14_model = CLIP_ViT_L_14()
vi_to_en_translator = VietnameseToEnglishTranslator()


vietnamese_input_text = "Đi làm mà sếp cứ giao việc, tui chỉ muốn hét: Tui là nhân viên, không phải siêu nhân!"
english_translated_text = vi_to_en_translator.translate(vietnamese_input_text)
vector_embedding = clip14_model.embed(english_translated_text)


print(f"Vietnamese text: {vietnamese_input_text}")
print(f"English translation: {english_translated_text}")
print(f"Vector embedding shape: {vector_embedding.shape}")
print(f"Vector embedding: {vector_embedding}")