import os
from pathlib import Path
from math import ceil
from typing import Optional
from google import genai
from google.genai import types
from disease_template import ALL_TEMPLATES

# ========= แก้ไขได้ง่าย: ค่าพื้นฐาน =========
MODEL_NAME = "gemini-2.5-flash"

# system_instruction: ใส่ “บทบาท/กติกา” ของโมเดล
SYSTEM_INSTRUCTION_TEXT = """You are a radiology report text generator.
Your task is to create realistic radiology-style findings and impressions related to inflammatory pneumonia.
Each output must be a fluent paragraph of 5-7 sentences long, plain text only (no JSON, no lists).
Follow these rules strictly:
- Use the provided ontology (group, subtypes, synonyms, typical findings, location notes).
- Use one template_variation per output, filling placeholders naturally.
- Expand placeholders {laterality}, {lobe}, {zone} with valid values.
- Do not include negative statements such as "No pleural effusion".
- Use cautious clinical language (e.g., compatible with, suggestive of, in keeping with, may reflect, possibly representing).
- Alternate between finding-first and impression-first ordering.
- Occasionally use two synonyms together (multi-synonym templates).
- In some outputs, integrate location notes for context.
- Ensure variation across subtypes, confidence phrases, and synonyms.
- Write in a professional radiology tone.
"""

# user_content: ใส่ “คำสั่งสร้างงาน” ต่อครั้ง เช่น สร้าง 50 ข้อความ
# เคล็ดลับ: จะเติมจำนวนต่อครั้งภายหลังด้วย format()
USER_CONTENT_TEMPLATE = """Generate {n_items} radiology-style paragraphs, each paragraph describing {disease_name}.
Use the schema's template_variations, placeholders, and ontology as a guide.
{template_variations}
Each paragraph must be 5–7 sentences long, with detailed elaboration of findings, impression, and explanatory context.
Output should be plain text only, one paragraph per output.
Separate each paragraph with a blank line.
"""


# ========= ฟังก์ชันหลัก =========
def generate_batch_outputs(
    system_instruction_text: str,
    user_content_template: str,
    template_variations_text: str,
    items_per_call: int,
    total_items: int,
    disease_name: str,
    out_root: str = "disease_output",
    temperature: float = 0.7,
    thinking_budget: int = 0,
    model_name: str = MODEL_NAME,
    api_key: Optional[str] = None,
):
    """
    เรียก Gemini หลายรอบจนได้จำนวนข้อความครบตาม total_items
    บันทึกผลครั้งละ 1 ไฟล์ (หนึ่งไฟล์ต่อหนึ่งครั้งที่เรียก API)

    โครงสร้างไฟล์: output/<disease_name>/<sequence>/<sequence>.txt
    เช่น: output/Inflammatory_Pneumonia/001/001.txt
    """
    if api_key is None:
        api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY. Set environment variable or pass api_key.")

    client = genai.Client(api_key=api_key)

    # เตรียม system_instruction
    system_instruction_parts = [types.Part.from_text(text=system_instruction_text)]

    # นับจำนวนรอบ
    num_calls = ceil(total_items / items_per_call)

    # โฟลเดอร์หลักของโรค
    base_dir = Path(out_root) / disease_name
    base_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, num_calls + 1):
        # คำนวณจำนวนที่ต้องการในรอบนี้ (รอบสุดท้ายอาจเหลือไม่เต็ม)
        remaining = total_items - (i - 1) * items_per_call
        n_this_call = min(items_per_call, remaining)

        # ทำ content สำหรับรอบนี้
        user_content_text = user_content_template.format(
            n_items=n_this_call,
            disease_name=disease_name,
            template_variations=template_variations_text,
        )

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_content_text)],
            )
        ]

        cfg = types.GenerateContentConfig(
            temperature=temperature,
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
            system_instruction=system_instruction_parts,
        )

        # เรียกแบบ non-stream (ไม่มี chunk)
        resp = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=cfg,
        )

        text_out = getattr(resp, "text", None)
        if not text_out:
            # บาง SDK version อาจอยู่ใน resp.candidates[0].content.parts
            # สำรอง: ดึงแบบ parts รวมเป็นข้อความ
            text_out = _extract_text_fallback(resp) or ""

        # สร้างโฟลเดอร์ย่อยตามลำดับ (เช่น 001, 002, ...)
        seq = f"{i:03d}"
        seq_dir = base_dir

        # บันทึกไฟล์ 1 ครั้ง ต่อ 1 call
        out_path = seq_dir / f"{seq}.txt"
        
        # ถ้ามีไฟล์อยู่แล้ว -> เลื่อนไป seq ถัดไปจนกว่าจะเจอไฟล์ที่ยังไม่มี
        while out_path.exists():
            i += 1
            seq = f"{i:03d}"
            out_path = seq_dir / f"{seq}.txt"
        
        out_path.write_text(text_out.strip(), encoding="utf-8")

        print(f"[Saved] {out_path}  (items ~ {n_this_call})")


def _extract_text_fallback(resp) -> str:
    """สำรอง: รวมข้อความจาก candidates/parts กรณี resp.text ไม่มี"""
    try:
        if hasattr(resp, "candidates") and resp.candidates:
            parts = []
            for p in getattr(resp.candidates[0].content, "parts", []) or []:
                if hasattr(p, "text") and p.text:
                    parts.append(p.text)
            return "\n".join(parts).strip()
    except Exception:
        pass
    return ""


# ========= ตัวอย่างการใช้งาน =========
if __name__ == "__main__":

    template_variations_example = ALL_TEMPLATES["chest_changes"]

    # กำหนดชื่อโรค/หมวดเพื่อใช้เป็นเส้นทางโฟลเดอร์
    disease_name = "Chest_Changes"

    # เรียกผลิตรวม 1000 รายการ โดยให้โมเดลสร้างครั้งละ 50
    generate_batch_outputs(
        system_instruction_text=SYSTEM_INSTRUCTION_TEXT,
        user_content_template=USER_CONTENT_TEMPLATE,
        template_variations_text=template_variations_example,
        items_per_call=50,      # สร้างต่อ call
        total_items=1000,        # จำนวนทั้งหมดที่ต้องการ
        disease_name=disease_name,
        temperature=0.7,
        thinking_budget=0,
        model_name=MODEL_NAME,
        api_key=os.environ['ENV_API_KEY'],  # หรือใส่สตริงคีย์ตรงนี้
    )
