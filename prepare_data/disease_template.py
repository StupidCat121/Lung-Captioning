# templates_chest_cxr.py
import json
from copy import deepcopy


# ---------- ส่วนกลางที่ใช้ร่วมกัน (เหมือนตัวอย่าง IPF) ----------
CONFIDENCE_PHRASES = [
    "Findings are compatible with",
    "Appearance is suggestive of",
    "Imaging features are in keeping with",
    "Findings may reflect",
    "Most consistent with",
    "Possibly representing"
]

TEMPLATE_VARIATIONS = [
    {"id": "T01","template": "{synonym} seen as {typical_finding}. {confidence_phrase} {subtype}.",
     "requires": ["synonym", "typical_finding", "confidence_phrase", "subtype"],
     "optional": [],"supports": {"order": "finding_first", "allow_multi_synonym": False}},
    {"id": "T02","template": "{confidence_phrase} {subtype}, with {synonym} demonstrated as {typical_finding}.",
     "requires": ["confidence_phrase", "subtype", "synonym", "typical_finding"],
     "optional": [],"supports": {"order": "impression_first", "allow_multi_synonym": False}},
    {"id": "T03","template": "{synonym1} / {synonym2} observed showing {typical_finding}. {confidence_phrase} {group}.",
     "requires": ["synonym1", "synonym2", "typical_finding", "confidence_phrase", "group"],
     "optional": [],"supports": {"order": "finding_first", "allow_multi_synonym": True}},
    {"id": "T04","template": "{confidence_phrase} {subtype}, characterized by {typical_finding}.",
     "requires": ["confidence_phrase", "subtype", "typical_finding"],
     "optional": [],"supports": {"order": "impression_first", "allow_multi_synonym": False}},
    {"id": "T05","template": "Imaging shows {synonym} corresponding to {typical_finding}; {confidence_phrase} {subtype}.",
     "requires": ["synonym", "typical_finding", "confidence_phrase", "subtype"],
     "optional": [],"supports": {"order": "either", "allow_multi_synonym": False}},
    {"id": "T06","template": "{typical_finding} is present, {confidence_phrase} {subtype}.",
     "requires": ["typical_finding", "confidence_phrase", "subtype"],
     "optional": [],"supports": {"order": "finding_first", "allow_multi_synonym": False}},
    {"id": "T07","template": "The pattern of {synonym} aligns with {typical_finding}. {confidence_phrase} {subtype}.",
     "requires": ["synonym", "typical_finding", "confidence_phrase", "subtype"],
     "optional": [],"supports": {"order": "finding_first", "allow_multi_synonym": False}},
    {"id": "T08","template": "Findings of {synonym} with {typical_finding} are in keeping with {subtype}.",
     "requires": ["synonym", "typical_finding", "subtype"],
     "optional": [],"supports": {"order": "finding_first", "allow_multi_synonym": False},
     "override_confidence_phrase": "Imaging features are in keeping with"},
    {"id": "T09","template": "Appearance demonstrates {synonym}, described as {typical_finding}; {confidence_phrase} {subtype}.",
     "requires": ["synonym", "typical_finding", "confidence_phrase", "subtype"],
     "optional": [],"supports": {"order": "either", "allow_multi_synonym": False}},
    {"id": "T10","template": "{confidence_phrase} {group}, likely representing {subtype}, supported by {typical_finding}.",
     "requires": ["confidence_phrase", "group", "subtype", "typical_finding"],
     "optional": [],"supports": {"order": "impression_first", "allow_multi_synonym": False}},
    {"id": "T11","template": "{synonym} involving {typical_finding}; {confidence_phrase} an acute {group}.",
     "requires": ["synonym", "typical_finding", "confidence_phrase", "group"],
     "optional": [],"supports": {"order": "either", "allow_multi_synonym": False}},
    {"id": "T12","template": "Radiographic features of {typical_finding} indicate {confidence_phrase} {subtype}.",
     "requires": ["typical_finding", "confidence_phrase", "subtype"],
     "optional": [],"supports": {"order": "finding_first", "allow_multi_synonym": False}},
    {"id": "T13","template": "{confidence_phrase} {subtype}, which commonly involves {location_note}; current imaging shows {synonym} as {typical_finding}.",
     "requires": ["confidence_phrase", "subtype", "location_note", "synonym", "typical_finding"],
     "optional": [],"supports": {"order": "impression_first", "allow_multi_synonym": False}},
    {"id": "T14","template": "{synonym1} / {synonym2} with {typical_finding}. {confidence_phrase} {subtype}.",
     "requires": ["synonym1", "synonym2", "typical_finding", "confidence_phrase", "subtype"],
     "optional": [],"supports": {"order": "finding_first", "allow_multi_synonym": True}},
]

RENDERING_RULES = {
    "nested_placeholder_expansion": {
        "typical_finding":
            "If {typical_finding} contains {laterality}, {lobe}, or {zone}, expand them before final rendering.",
        "laterality_lobe_rules": [
            "If lobe == 'middle lobe', laterality must be 'right'.",
            "If laterality == 'bilateral', do not combine with a single lobe unless explicitly specified."
        ]
    },
    "text_case": {"sentence_start_capital": True, "proper_nouns_capital": True},
    "punctuation": {"ensure_terminal_period": True, "deduplicate_spaces": True},
    "synonym_constraints": [
        "When using synonym1/synonym2, they must be distinct.",
        "Avoid pairing 'air bronchogram' with itself as synonym2."
    ],
    "fallbacks": {
        "missing_subtype": "Use {group} instead of {subtype}.",
        "missing_confidence_phrase": "Default to 'Findings are compatible with'."
    }
}

PLACEHOLDERS_BLOCK = {
    "group": "e.g., 'Inflammatory processes (pneumonia)'",
    "subtype": "One of: 'Lobar pneumonia', 'Bronchopneumonia (patchy)', 'Atypical/interstitial pneumonia', 'Aspiration pneumonia', 'Organizing pneumonia'",
    "synonym": "One item from synonyms[]",
    "synonym1": "One item from synonyms[] (distinct from synonym2 when both used)",
    "synonym2": "One item from synonyms[] (distinct from synonym1 when both used)",
    "typical_finding": "One item from typical_findings[] (may contain nested {laterality}, {lobe}, {zone})",
    "confidence_phrase": "One item from confidence_phrases[]",
    "laterality": "One of: 'right', 'left', 'bilateral'",
    "lobe": "One of: 'upper lobe', 'middle lobe', 'lower lobe' (RML only on right)",
    "zone": "One of: 'upper zone', 'mid zone', 'lower zone'",
    "location_note": "One item from location_notes[]"
}


def make_schema(schema_name: str, ontology_binding: dict, description: str = None) -> str:
    """ประกอบสคีมาเป็นสตริง JSON (indent=2)"""
    payload = {
        "schema_version": "1.0",
        "name": schema_name,
        "description": description or (
            "Schema for generating radiology-style sentences from ontology fields "
            "using flexible template variations."
        ),
        "placeholders": PLACEHOLDERS_BLOCK,
        "confidence_phrases": CONFIDENCE_PHRASES,
        "template_variations": TEMPLATE_VARIATIONS,
        "rendering_rules": RENDERING_RULES,
        "ontology_binding": ontology_binding,
        "example_generation_note": (
            "To generate, select one template_variation, expand placeholders using "
            "ontology_binding and placeholders, then apply rendering_rules."
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------- บล็อก ontology ทั้ง 9 ตามข้อมูลที่ให้ ----------
ONTO_1_NORMAL = {
    "id": "1_normal",
    "group": "Normal",
    "subtypes": [
        "Normal chest radiograph",
        "No acute cardiopulmonary disease",
        "No focal consolidation",
        "No pleural effusion",
        "No pneumothorax"
    ],
    "synonyms": [
        "unremarkable chest radiograph",
        "within normal limits (WNL)",
        "no acute cardiopulmonary process",
        "clear lungs",
        "no focal air-space disease",
        "no active pulmonary disease",
        "no acute osseous abnormality",
        "no acute findings"
    ],
    "typical_findings": [
        "Lungs are clear without focal consolidation or interstitial edema.",
        "Cardiomediastinal silhouette within normal size for {view}.",
        "Costophrenic angles are sharp; no pleural effusion identified.",
        "No pneumothorax; lung markings extend to the chest wall.",
        "No acute osseous abnormality of the visualized thorax.",
        "No acute cardiopulmonary findings are seen."
    ],
    "location_notes": [
        "Applies to all lobes and zones.",
        "Confirm projection: {view} (PA preferred for cardiac size)."
    ]
}

ONTO_2_IP = {
    "id": "2_inflammatory_pneumonia",
    "group": "Inflammatory processes (pneumonia)",
    "subtypes": [
        "Lobar pneumonia",
        "Bronchopneumonia (patchy)",
        "Atypical/interstitial pneumonia",
        "Aspiration pneumonia",
        "Organizing pneumonia"
    ],
    "synonyms": [
        "air-space disease",
        "alveolar consolidation",
        "parenchymal opacity",
        "infectious consolidation",
        "air bronchogram",
        "parapneumonic change",
        "inflammatory infiltrate",
        "parenchymal infiltrate"
    ],
    "typical_findings": [
        "Focal air-space opacity in the {laterality} {lobe}/{zone} with air bronchograms.",
        "Patchy peribronchial opacities in a multifocal distribution.",
        "Confluent consolidation with silhouetting of adjacent cardiac or diaphragmatic borders (silhouette sign).",
        "Basilar predominant consolidation, greater on the {laterality}, compatible with aspiration pattern.",
        "Interstitial/perihilar opacities suggestive of atypical infectious process."
    ],
    "location_notes": [
        "Aspiration often involves dependent lobes (right lower > left lower, right middle).",
        "Lobar pneumonia may silhouette adjacent structures (e.g., RML with right heart border)."
    ]
}

ONTO_3_HDENS = {
    "id": "3_higher_density",
    "group": "Higher density (pleural effusion, atelectatic consolidation, hydrothorax, empyema)",
    "subtypes": [
        "Pleural effusion (including subpulmonic)",
        "Hydrothorax",
        "Empyema (loculated pleural collection)",
        "Atelectatic consolidation",
        "Hydropneumothorax (if present)"
    ],
    "synonyms": [
        "pleural fluid",
        "meniscus sign",
        "blunting of costophrenic angle",
        "subpulmonic effusion",
        "loculated pleural collection",
        "split pleura sign (CT correlate)",
        "volume loss (for atelectasis)",
        "fissure displacement (for atelectasis)"
    ],
    "typical_findings": [
        "Blunting of the {laterality} costophrenic angle with meniscus configuration.",
        "Homogeneous opacity layering along the pleural space, greater on {laterality}.",
        "Subpulmonic effusion suggested by elevated {laterality} hemidiaphragm contour.",
        "Lobar/segmental atelectasis with volume loss, fissure shift, and crowding of bronchovascular markings.",
        "Empyema suspected when a lenticular pleural-based opacity forms obtuse angles with the chest wall (often loculated).",
        "Cardiomediastinal shift toward the side of atelectasis (if significant volume loss)."
    ],
    "location_notes": [
        "Pleural effusions layer dependently; assess costophrenic angles and lateral views.",
        "Atelectasis patterns: RUL (upward minor fissure), RML (silhouettes right heart), RLL/LLL (posterior basal)."
    ]
}

ONTO_4_LDENS = {
    "id": "4_lower_density",
    "group": "Lower density (pneumothorax, pneumomediastinum, pneumoperitoneum)",
    "subtypes": ["Pneumothorax", "Pneumomediastinum", "Pneumoperitoneum"],
    "synonyms": [
        "PTX (pneumothorax)",
        "collapsed lung",
        "mediastinal emphysema",
        "free intraperitoneal air",
        "subdiaphragmatic free air",
        "deep sulcus sign (supine PTX)",
        "continuous diaphragm sign (pneumomediastinum)",
        "visceral pleural line"
    ],
    "typical_findings": [
        "Visceral pleural line with absent peripheral lung markings on the {laterality} side.",
        "Deep sulcus sign in the {laterality} hemithorax on supine film suggestive of pneumothorax.",
        "Linear lucency outlining mediastinal structures with continuous diaphragm sign (pneumomediastinum).",
        "Free air beneath the hemidiaphragms, more evident under the {laterality} dome (pneumoperitoneum).",
        "No associated pleural effusion unless hydropneumothorax is present.",
        "Degree of collapse may vary; tension physiology is a clinical diagnosis (look for mediastinal shift)."
    ],
    "location_notes": [
        "Pneumothorax collects anteromedially and apically on upright films; deep sulcus sign on supine.",
        "Pneumoperitoneum seen as free air under diaphragms (upright) or Rigler sign (supine)."
    ]
}

ONTO_5_OBS = {
    "id": "5_obstructive",
    "group": "Obstructive pulmonary diseases (emphysema, bronchopneumonia, bronchiectasis, embolism)",
    "subtypes": [
        "Emphysema/COPD",
        "Bronchopneumonia (patchy infection)",
        "Bronchiectasis",
        "Pulmonary embolism (PE) — CXR often non-specific"
    ],
    "synonyms": [
        "hyperinflation",
        "flattened diaphragms",
        "increased retrosternal airspace (lateral film)",
        "tram-track opacities (bronchiectasis)",
        "ring shadows (bronchiectasis)",
        "patchy air-space opacities (bronchopneumonia)",
        "Hampton hump (rare PE sign)",
        "Westermark sign (rare PE sign)"
    ],
    "typical_findings": [
        "Hyperinflated lungs with flattened diaphragms and increased anteroposterior diameter.",
        "Attenuated peripheral vascular markings consistent with emphysematous change.",
        "Tram-track and ring-like opacities suggestive of bronchiectasis (CT correlation often needed).",
        "Patchy peribronchial air-space opacities consistent with bronchopneumonia.",
        "CXR may be normal in pulmonary embolism; when present, peripheral wedge-shaped opacity may be seen (Hampton hump).",
        "No large pleural effusion or pneumothorax unless specified."
    ],
    "location_notes": [
        "Emphysema often shows basilar flattening of diaphragms and hyperlucent lungs.",
        "Bronchiectasis can be focal or diffuse; look for lower-lobe predominance in some etiologies."
    ]
}

ONTO_6_DEGEN_INF = {
    "id": "6_degenerative_infectious",
    "group": "Degenerative infectious diseases (tuberculosis, sarcoidosis, proteinosis, fibrosis)",
    "subtypes": [
        "Pulmonary tuberculosis (post-primary/primary)",
        "Sarcoidosis",
        "Pulmonary alveolar proteinosis (PAP)",
        "Pulmonary fibrosis (e.g., IPF pattern on CXR)"
    ],
    "synonyms": [
        "upper-lobe cavitation (TB)",
        "tree-in-bud nodularity (CT correlate for TB)",
        "bilateral hilar lymphadenopathy (sarcoidosis)",
        "reticulonodular pattern",
        "interstitial fibrosis",
        "honeycombing (CT correlate)",
        "crazy-paving pattern (PAP on CT; alveolar filling on CXR)",
        "volume loss with coarse reticulation"
    ],
    "typical_findings": [
        "Upper-lobe predominant opacities with possible cavitation suggestive of post-primary TB.",
        "Bilateral, symmetric hilar enlargement with perihilar reticulonodular changes (sarcoidosis).",
        "Diffuse alveolar opacities that may appear perihilar (PAP), often with relative peripheral sparing.",
        "Coarse reticular opacities with volume loss, basilar and peripheral predominance (fibrotic pattern on CXR).",
        "Calcified granulomas or lymph nodes may be present in chronic granulomatous disease.",
        "No large pleural effusion unless otherwise specified."
    ],
    "location_notes": [
        "TB often favors apical/posterior upper lobes and superior segments of lower lobes.",
        "Fibrosis frequently shows basilar and peripheral (subpleural) predominance on CXR."
    ]
}

ONTO_7_ENCAP = {
    "id": "7_encapsulated_lesions",
    "group": "Encapsulated lesions (abscesses, nodules, cysts, tumor masses, metastases)",
    "subtypes": [
        "Lung abscess (cavity with air-fluid level)",
        "Solitary pulmonary nodule",
        "Pulmonary cyst",
        "Primary lung mass",
        "Pulmonary metastases"
    ],
    "synonyms": [
        "cavitary lesion",
        "air–fluid level",
        "coin lesion (solitary nodule)",
        "cannonball metastases",
        "rounded opacity",
        "spiculated mass",
        "thin-walled cyst",
        "well-circumscribed nodule"
    ],
    "typical_findings": [
        "Round or oval opacity measuring {size} with well- or ill-defined margins.",
        "Cavitary lesion with an air–fluid level, often in dependent portions (abscess).",
        "Multiple rounded nodules of varying sizes suggestive of metastatic disease.",
        "Spiculated, irregular mass concerning for primary lung malignancy.",
        "Thin-walled cystic lucency; wall thickness and internal content to be correlated with CT.",
        "No pleural effusion or pneumothorax unless tumor-related complications are present."
    ],
    "location_notes": [
        "Nodules/masses may occur in any lobe; metastatic nodules are often multiple and peripheral.",
        "Abscesses may occur posteriorly/dependently; look for air–fluid levels."
    ]
}

ONTO_8_MEDIA = {
    "id": "8_mediastinal_changes",
    "group": "Mediastinal changes (pericarditis, arteriovenous malformations, lymph node enlargement)",
    "subtypes": [
        "Pericardial effusion/pericarditis (CXR signs)",
        "Arteriovenous malformations (pulmonary AVM may project as nodular opacity)",
        "Mediastinal/hilar lymphadenopathy"
    ],
    "synonyms": [
        "enlarged cardiac silhouette (pericardial effusion)",
        "water-bottle heart configuration",
        "mediastinal widening",
        "bilateral hilar fullness",
        "pulmonary AVM (feeding/draining vessel on CT)",
        "aorticopulmonary window opacity",
        "right paratracheal stripe prominence",
        "lymph node enlargement"
    ],
    "typical_findings": [
        "Globally enlarged cardiac silhouette out of proportion to clinical status, suggestive of pericardial effusion (best on PA).",
        "Mediastinal widening or focal right paratracheal stripe prominence indicating possible nodal enlargement.",
        "Bilateral hilar fullness consistent with adenopathy (e.g., sarcoidosis, lymphoma, infection).",
        "Well-circumscribed nodular opacity with suspected vascular connections may reflect pulmonary AVM (confirm on CT/angio).",
        "No pulmonary edema or focal consolidation unless otherwise specified.",
        "Silhouette of aorticopulmonary window may be obscured by nodal enlargement."
    ],
    "location_notes": [
        "Hilar and mediastinal nodes: right paratracheal, subcarinal, aortopulmonary window, bilateral hila.",
        "Cardiac silhouette assessment is projection-dependent (PA vs AP)."
    ]
}

ONTO_9_CHEST = {
    "id": "9_chest_changes",
    "group": "Chest changes (atelectasis, malformations, agenesis, hypoplasia)",
    "subtypes": [
        "Atelectasis (lobar/segmental)",
        "Congenital malformations",
        "Pulmonary agenesis/aplasia",
        "Pulmonary hypoplasia"
    ],
    "synonyms": [
        "volume loss",
        "fissure displacement",
        "crowding of vessels/bronchi",
        "mediastinal shift toward opacity",
        "compensatory hyperinflation",
        "congenital anomaly",
        "absent lung/hemithorax",
        "small hypoplastic lung"
    ],
    "typical_findings": [
        "Lobar opacity with volume loss evidenced by fissure shift and crowding of bronchovascular markings.",
        "Mediastinal shift toward the affected side in significant atelectasis.",
        "Compensatory hyperinflation of the contralateral lung.",
        "Marked asymmetry of lung volumes suggesting agenesis/aplasia or severe hypoplasia.",
        "Thoracic cage asymmetry and elevation of hemidiaphragm on the affected side.",
        "No pleural effusion or pneumothorax unless otherwise stated."
    ],
    "location_notes": [
        "Atelectasis patterns: RUL (elevated minor fissure), RML (silhouettes right heart border), LLL/RLL (posterior basal).",
        "Agenesis/hypoplasia: small hemithorax with mediastinal shift toward the affected side."
    ]
}


# ---------- ประกอบเป็นตัวแปร 9 เวอร์ชัน (สตริง JSON) ----------
template_Normal = make_schema(
    schema_name="Normal_Template_Variations",
    ontology_binding=ONTO_1_NORMAL,
    description=("Schema for generating radiology-style sentences for normal CXR reports "
                 "using flexible template variations.")
)

template_Inflammatory_Pneumonia = make_schema(
    schema_name="Inflammatory_Pneumonia_Template_Variations",
    ontology_binding=ONTO_2_IP,
    description=("Schema for generating radiology-style sentences (inflammatory pneumonia) "
                 "from ontology fields using flexible template variations.")
)

template_Higher_Density = make_schema(
    schema_name="Higher_Density_Template_Variations",
    ontology_binding=ONTO_3_HDENS
)

template_Lower_Density = make_schema(
    schema_name="Lower_Density_Template_Variations",
    ontology_binding=ONTO_4_LDENS
)

template_Obstructive = make_schema(
    schema_name="Obstructive_Diseases_Template_Variations",
    ontology_binding=ONTO_5_OBS
)

template_Degenerative_Infectious = make_schema(
    schema_name="Degenerative_Infectious_Template_Variations",
    ontology_binding=ONTO_6_DEGEN_INF
)

template_Encapsulated_Lesions = make_schema(
    schema_name="Encapsulated_Lesions_Template_Variations",
    ontology_binding=ONTO_7_ENCAP
)

template_Mediastinal_Changes = make_schema(
    schema_name="Mediastinal_Changes_Template_Variations",
    ontology_binding=ONTO_8_MEDIA
)

template_Chest_Changes = make_schema(
    schema_name="Chest_Changes_Template_Variations",
    ontology_binding=ONTO_9_CHEST
)


# ---------- (ตัวเลือก) รวมเป็นดิกชันนารีสำหรับอ้างอิงแบบชื่อ ----------
ALL_TEMPLATES = {
    "normal": template_Normal,
    "inflammatory_pneumonia": template_Inflammatory_Pneumonia,
    "higher_density": template_Higher_Density,
    "lower_density": template_Lower_Density,
    "obstructive": template_Obstructive,
    "degenerative_infectious": template_Degenerative_Infectious,
    "encapsulated_lesions": template_Encapsulated_Lesions,
    "mediastinal_changes": template_Mediastinal_Changes,
    "chest_changes": template_Chest_Changes,
}


if __name__ == "__main__":
    # ตัวอย่างการใช้งาน/ทดสอบพิมพ์ชื่อ keys และความยาวแต่ละสตริง
    print(list(ALL_TEMPLATES.keys()))
    for k, v in ALL_TEMPLATES.items():
        print(k, "len:", len(v))
