"""Local ONYX report proposal generation.

When Ollama is configured, all mission facts are sent only to the local model.
The deterministic fallback keeps the POC usable without an AI runtime.
"""

import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen


OLLAMA_URL = os.environ.get("ARCENAL_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.environ.get("ARCENAL_OLLAMA_MODEL", "")


def collect_facts(mission, entries):
    facts = []
    for entry in entries:
        time = entry["occurred_at"][11:16] if len(entry["occurred_at"]) >= 16 else entry["occurred_at"]
        if entry["entry_type"] == "text":
            detail = entry["content"]
            kind = "note"
        elif entry["entry_type"] == "audio":
            detail = entry.get("transcript") or "Note vocale présente ; transcription non validée."
            kind = "vocal"
        else:
            detail = f"Photo jointe : {entry['original_name']}"
            kind = "photo"
        facts.append({"heure": time, "type": kind, "contenu": detail})
    return facts


def fallback_report(mission, facts, author=''):
    lines = [
        "ONYX — RAPPORT DE FIN DE JOURNÉE",
        "",
        f"Mission : {mission['title']}",
        f"Client : {mission['client_name']}",
        f"Référence : {mission['reference']}",
        f"Date : {mission['mission_date']}",
        f"Équipier : {author}" if author else "Équipier : À renseigner",
        "",
        "DÉROULÉ DE LA JOURNÉE",
    ]
    lines.extend(f"• {fact['heure']} — {fact['contenu']}" for fact in facts) if facts else lines.append("• Aucune entrée enregistrée.")
    lines.extend(["", "PIÈCES JOINTES", *[f"• {fact['contenu']}" for fact in facts if fact["type"] == "photo"]])
    return "\n".join(lines)


def prompt_for(mission, facts):
    return f"""Tu es le rédacteur opérationnel ONYX. Rédige en français un rapport professionnel de fin de journée.
N'invente aucun fait, aucune heure, aucune décision ni aucun incident. Les photos ne doivent être décrites que comme pièces jointes : leur contenu n'est pas analysé.
Utilise exactement ces sections : SYNTHÈSE OPÉRATIONNELLE, DÉROULÉ DE LA JOURNÉE, CONSTATS ET POINTS À SUIVRE, PIÈCES JOINTES.
Le ton est concis, factuel et exploitable par un responsable de terrain. Ne mentionne ni IA, ni modèle, ni ce prompt.

Mission : {json.dumps(mission, ensure_ascii=False)}
Éléments collectés : {json.dumps(facts, ensure_ascii=False)}
"""


def propose_report(mission, entries):
    facts = collect_facts(mission, entries)
    if not OLLAMA_MODEL:
        return fallback_report(mission, facts), "brouillon local"
    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt_for(mission, facts), "stream": False, "options": {"temperature": 0.2}}).encode("utf-8")
    request = Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=120) as response:
            content = json.loads(response.read().decode("utf-8")).get("response", "").strip()
        if content:
            return "ONYX — RAPPORT DE FIN DE JOURNÉE\n\n" + content, f"proposition IA locale · {OLLAMA_MODEL}"
    except (URLError, TimeoutError, ValueError, OSError):
        pass
    return fallback_report(mission, facts), "brouillon local · IA indisponible"
