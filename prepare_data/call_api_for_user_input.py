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
SYSTEM_INSTRUCTION_TEXT = """You are a professional prompt generator for clinical datasets.  
Your task is to create user-style input texts that always include the placeholder {clinical_text}.  

Rules:  
- Each output must keep {clinical_text} exactly as written (do not change, shorten, or add details).  
- Do not invent or add new information (e.g., age, gender, duration, medical history).  
- The text does not need to be in first person. It can be a question, statement, or request, but must sound natural and realistic for clinical or radiology use cases.  
- Produce outputs in batches of 100 unique variations per request.  
- Each output should be a single text only, without numbering, bullets, or extra explanation.  
- Each text must be {sentences_long} sentences long, with varied phrasing and structure, but always relevant to {clinical_text} and chest X-ray interpretation.
"""

# user_content: ใส่ “คำสั่งสร้างงาน” ต่อครั้ง เช่น สร้าง 50 ข้อความ
# เคล็ดลับ: จะเติมจำนวนต่อครั้งภายหลังด้วย format()
USER_CONTENT_TEMPLATE = """Generate {n_items} unique user input texts based on the following clinical description: {clinical_text}

Requirements:  
1. Every output must contain {clinical_text} exactly as given.  
2. Each text must be {sentences_long} sentences long.  
3. The texts must be natural, realistic, and relevant to asking about or describing chest X-ray findings.  
4. Do not add new details (e.g., age, gender, time duration).  
5. Output only the texts, no numbering, no list format, no explanation.  
"""


# ========= ฟังก์ชันหลัก =========
def generate_batch_outputs(
    system_instruction_text: str,
    user_content_template: str,
    items_per_call: int,
    total_items: int,
    sentences_long: int,
    out_root: str = "output",
    temperature: float = 1,
    thinking_budget: int = 0,
    model_name: str = MODEL_NAME,
    api_key: Optional[str] = None,
    clinical_text: str = "{clinical_text}",
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
    system_instruction_format = system_instruction_text.format(
        clinical_text=clinical_text,
        sentences_long=sentences_long,
    )
    system_instruction_parts = [types.Part.from_text(text=system_instruction_format)]

    # นับจำนวนรอบ
    num_calls = ceil(total_items / items_per_call)

    # โฟลเดอร์หลัก
    base_dir = Path(out_root)
    base_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, num_calls + 1):
        # คำนวณจำนวนที่ต้องการในรอบนี้ (รอบสุดท้ายอาจเหลือไม่เต็ม)
        remaining = total_items - (i - 1) * items_per_call
        n_this_call = min(items_per_call, remaining)

        # ทำ content สำหรับรอบนี้
        user_content_text = user_content_template.format(
            n_items=n_this_call,
            clinical_text=clinical_text,
            sentences_long=sentences_long,
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

        # บันทึกไฟล์ 1 ครั้ง ต่อ 1 call
        seq = f"{i:03d}"
        out_path = base_dir / f"sl{sentences_long}_{seq}.txt"

        # ถ้ามีไฟล์อยู่แล้ว -> เลื่อนไป seq ถัดไปจนกว่าจะเจอไฟล์ที่ยังไม่มี
        while out_path.exists():
            i += 1
            seq = f"{i:03d}"
            out_path = base_dir / f"sl{sentences_long}_{seq}.txt"

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

    generate_batch_outputs(
        system_instruction_text=SYSTEM_INSTRUCTION_TEXT,
        user_content_template=USER_CONTENT_TEMPLATE,
        items_per_call=100,      # สร้างต่อ call
        total_items=500,        # จำนวนทั้งหมดที่ต้องการ
        sentences_long=5,
        out_root="userinput_output",
        temperature=1,
        thinking_budget=0,
        model_name=MODEL_NAME,
        api_key=os.environ['ENV_API_KEY'],  # หรือใส่สตริงคีย์ตรงนี้
    )
