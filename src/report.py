"""Text built from registry fields with templates. No LLM."""

from schemas import TrialSummary


def format_phase(phases: list[str]) -> str:
    """["PHASE2", "PHASE3"] -> "Phase 2/3"; ["EARLY_PHASE1"] -> "Early phase 1"; [] or ["NA"] -> ""."""
    if phases == ["EARLY_PHASE1"]:
        return "Early phase 1"
    numbers = [p.removeprefix("PHASE") for p in phases if p.startswith("PHASE")]
    return "Phase " + "/".join(numbers) if numbers else ""


def registry_summary(t: TrialSummary) -> str:
    """E.g. "Phase 2/3 trial of Acthar. Registry dates: 2017-06 to 2019-11. Status: terminated." """
    phase = format_phase(t.phases)
    kind = f"{phase} trial" if phase else "Trial"
    drugs = ", ".join(n for n in t.interventions if "placebo" not in n.lower())
    start = (t.start_date or "?")[:7]  # "2017-06-22" -> "2017-06"
    end = (t.completion_date or "?")[:7]
    status = t.overall_status.replace("_", " ").lower()
    return f"{kind} of {drugs or 'unnamed intervention'}. Registry dates: {start} to {end}. Status: {status}."


def print_summary(t: TrialSummary) -> None:
    """Short console view of one trial: registry line, stop category, cited claims."""
    print(f"  {registry_summary(t)}")
    if t.stop_category:
        print(f"  stop category: {t.stop_category}")
    if t.search_note:
        print(f"  search note: {t.search_note}")
    if not t.claims:
        print("  (no claims)")
    for c in t.claims:
        refs = ", ".join(s.reference for s in c.sources)
        print(f"  - [{c.topic}] {c.text}\n      sources: {refs}")
