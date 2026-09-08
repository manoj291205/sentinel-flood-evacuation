#!/usr/bin/env python3
"""Build the construction-labeled Phase 14A claim-support challenge artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.constraints.claim_support import get_chunk_by_id, label_independent_order  # noqa: E402
from src.rag.ingest import prepare_corpus  # noqa: E402

PHASE13 = ROOT / "data" / "eval_v3" / "phase13"
PHASE14 = ROOT / "data" / "eval_v3" / "phase14"
QUESTIONS_PATH = PHASE13 / "retained_question_review.csv"
LABELS_PATH = PHASE13 / "ai_assisted_passage_labels_extended.csv"
CHALLENGE_PATH = PHASE14 / "claim_support_challenge.json"
MANIFEST_PATH = PHASE14 / "claim_support_manifest.json"
SPOTCHECK_PATH = PHASE14 / "claim_support_spotcheck.json"
REVIEW_PATH = ROOT / "V3_CLAIM_SUPPORT_CHALLENGE_REVIEW.md"

BENCHMARK_VERSION = "v3-claim-support-challenge-v1"
CONSTRUCTION_PROTOCOL_VERSION = "v3-claim-support-construction-v1"
SOURCE_BENCHMARK_VERSION = "v3-retrieval-benchmark-ai-assisted-v2"
SOURCE_LABEL_FINGERPRINT = "393512866c33a32d9aa2944289791eb74554eeb585e21cc82956be203c28b1b7"
CORPUS_VERSION = "v3-authoritative-corpus-v1"
CORPUS_FINGERPRINT = "a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753"

LABELS = ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED")
REASON_SUBTYPES = (
    "SUPPORTED_PARAPHRASE", "UNSUPPORTED_ADDITION", "MODALITY_OVERSTATEMENT",
    "SCOPE_OVERSTATEMENT", "ACTOR_MISMATCH", "TIMING_ADDITION", "NUMERIC_ADDITION",
    "CONDITION_ADDITION", "CONTRADICTION", "SAME_TOPIC_WRONG_CLAIM",
    "POPULATION_MISMATCH", "OTHER",
)
CANONICAL_FIELDS = (
    "claim_pair_id", "question_id", "effective_question", "chunk_id", "source_id",
    "filename", "page", "passage_sha256", "claim", "construction_label",
    "construction_reason", "reason_subtype", "synthetic_variant",
    "not_authoritative_policy", "benchmark_version", "construction_protocol_version",
)

# Every tuple is (claim, subtype, construction reason). These are controlled benchmark
# constructions, not authoritative guidance. All supported rows are concise paraphrases;
# partial and unsupported rows deliberately introduce realistic LLM-style errors.
CLAIMS: dict[str, tuple[tuple[str, str, str], tuple[str, str, str], tuple[str, str, str]]] = {
    "Q001": (
        ("Flood-plain zoning reduces damage by limiting inappropriate development where rivers naturally overflow.", "SUPPORTED_PARAPHRASE", "Paraphrases the passage's link between unplanned flood-plain use and flood damage."),
        ("Flood-plain zoning reduces damage by limiting inappropriate development and permanently prevents rivers from overflowing.", "UNSUPPORTED_ADDITION", "The development-control point is supported, but permanent prevention of overflow is not."),
        ("Flood-plain zoning reduces losses by encouraging dense construction beside river channels.", "CONTRADICTION", "The passage warns that unplanned flood-plain development increases damage."),
    ),
    "Q002": (
        ("Flood warnings should give understandable information on current and expected water levels, inundated areas, depth, and duration.", "SUPPORTED_PARAPHRASE", "Restates the listed information and accessibility requirement."),
        ("Flood warnings should provide those details through mandatory hourly smartphone alerts.", "TIMING_ADDITION", "The warning content is supported, but an hourly smartphone schedule is absent."),
        ("Flood warnings need report only historical rainfall totals, not expected inundation.", "CONTRADICTION", "The passage explicitly calls for expected water levels and likely inundation."),
    ),
    "Q003": (
        ("Flood disaster relief centres and essential facilities should be placed on high ground so they remain functional during floods.", "SUPPORTED_PARAPHRASE", "Faithfully paraphrases the siting recommendation."),
        ("All flood relief facilities must be placed at least ten metres above the nearest river.", "NUMERIC_ADDITION", "High-ground siting is supported; the universal ten-metre threshold is invented."),
        ("Flood disaster relief centres should be located in low-lying river corridors for easier water access.", "CONTRADICTION", "This reverses the high-ground recommendation."),
    ),
    "Q005": (
        ("Unplanned flood-plain development and waterway encroachment increase flood risk and losses.", "SUPPORTED_PARAPHRASE", "Directly paraphrases the stated causal relationship."),
        ("Every flood-plain development inevitably causes catastrophic loss within one year.", "SCOPE_OVERSTATEMENT", "The passage supports increased risk, not inevitability, universal scope, or a deadline."),
        ("Encroaching on waterways reduces flood risk by containing development near rivers.", "CONTRADICTION", "The evidence states that encroachment increases risk and losses."),
    ),
    "Q006": (
        ("Scenario analysis and simulation can strengthen long-term flood preparedness, mitigation, and response planning.", "SUPPORTED_PARAPHRASE", "Restates the uses assigned to scenario analysis and simulation."),
        ("Simulation guarantees accurate flood outcomes even when built-environment data are unavailable.", "MODALITY_OVERSTATEMENT", "The passage calls simulation useful and warns that missing data creates assumption-based scenarios."),
        ("Authorities should avoid scenario modelling because it weakens long-term flood preparedness.", "CONTRADICTION", "This reverses the passage's assessment of modelling."),
    ),
    "Q008": (
        ("Flood-warning information should be presented in a way that affected people can readily understand.", "SUPPORTED_PARAPHRASE", "Paraphrases the communication requirement."),
        ("Warnings must be understandable and issued only in English through a national mobile application.", "UNSUPPORTED_ADDITION", "Understandability is supported; the language and channel restrictions are not."),
        ("Technical flood warnings should remain inaccessible to the public until flooding has ended.", "CONTRADICTION", "The passage requires public-domain warnings with lead time."),
    ),
    "Q009": (
        ("Planners should identify dependable road, rail, and communication links between relief or supply centres and flood-prone areas.", "SUPPORTED_PARAPHRASE", "Restates the infrastructure connections named in the passage."),
        ("Every relief corridor must include a new six-lane highway and dedicated freight railway.", "SCOPE_OVERSTATEMENT", "The passage supports reliable links and possible new infrastructure, not these universal specifications."),
        ("Relief planning should ignore transport links and rely exclusively on air delivery.", "SAME_TOPIC_WRONG_CLAIM", "Air-only delivery is not established and conflicts with identifying road and rail networks."),
    ),
    "Q010": (
        ("The magnitude and severity of a flood should determine the response scale and whether district, state, or national actors are mobilised.", "SUPPORTED_PARAPHRASE", "Paraphrases the scale-and-role criterion."),
        ("Only the national government may decide every flood response, regardless of severity.", "ACTOR_MISMATCH", "The evidence assigns roles across district, state, and national levels according to the event."),
        ("Response scale should be chosen solely from the number of media reports about the flood.", "SAME_TOPIC_WRONG_CLAIM", "Media volume is not the stated basis for response scale."),
    ),
    "Q012": (
        ("Flood response arrangements should cover relief supplies, rescue equipment, water pumps, transport, logistics, and support for essential services.", "SUPPORTED_PARAPHRASE", "Summarises the resources listed for emergency response."),
        ("Authorities must keep exactly 500 water pumps in every district before monsoon season.", "NUMERIC_ADDITION", "Water pumps are supported, but the number, universal scope, and deadline are absent."),
        ("Flood rescue operations should exclude transport and logistics resources.", "CONTRADICTION", "The passage expressly includes transport and logistics."),
    ),
    "Q013": (
        ("Evacuation plans should define organisation-specific responsibilities and validate the participating organisations' plans.", "SUPPORTED_PARAPHRASE", "Captures the SOP responsibility and plan-validation requirements."),
        ("Each organisation's evacuation plan must be retested every seven days by the national government.", "TIMING_ADDITION", "Plan validation is supported, but the frequency and actor are invented."),
        ("Emergency evacuation works best when organisational responsibilities remain undecided until impact.", "CONTRADICTION", "The passage says responsibilities need to be fixed beforehand."),
    ),
    "Q015": (
        ("Industrial emergency planning should provide wide roads and multiple routes for responder access and escape.", "SUPPORTED_PARAPHRASE", "Restates the route and access provision."),
        ("Every industrial evacuation road must be at least thirty metres wide.", "NUMERIC_ADDITION", "Wide roads are supported, but no width threshold appears."),
        ("Industrial emergency areas should use one restricted route for both entry and escape.", "CONTRADICTION", "The passage calls for multiple routes."),
    ),
    "Q016": (
        ("State governments and disaster authorities should make emergency resuscitation equipment and drugs available, while hospitals maintain disaster plans.", "SUPPORTED_PARAPHRASE", "Paraphrases the two patient-evacuation preparedness requirements in the chunk."),
        ("Every patient evacuation must include two doctors and one ventilator per patient.", "NUMERIC_ADDITION", "Medical resources are supported, but these staffing and equipment ratios are not."),
        ("Hospitals do not need disaster plans if emergency drugs are available.", "CONTRADICTION", "The evidence separately requires hospital disaster plans."),
    ),
    "Q017": (
        ("District planning may identify older people without family support and arrange assistance for their food, medicine, shelter, and personal needs.", "SUPPORTED_PARAPHRASE", "Restates the elderly-support measures in the evidence."),
        ("All older residents must be permanently relocated outside their communities after any hazard warning.", "SCOPE_OVERSTATEMENT", "The passage prefers community support and discusses temporary arrangements based on severity."),
        ("Older people should always be grouped with everyone else because they have no distinct post-disaster needs.", "CONTRADICTION", "The passage says their needs should be considered separately."),
    ),
    "Q018": (
        ("People may need evacuation after flooding to move them from affected areas to safer surroundings.", "SUPPORTED_PARAPHRASE", "Direct paraphrase of the post-impact evacuation circumstance."),
        ("After any water enters a community, every resident must be moved within thirty minutes.", "TIMING_ADDITION", "Post-flood evacuation may be necessary, but the universal trigger and deadline are absent."),
        ("Once an area is flooded, residents should never be moved to safer surroundings.", "CONTRADICTION", "This reverses the post-flood evacuation guidance."),
    ),
    "Q020": (
        ("Multiple routes help provide reliable access for responders and escape pathways from an industrial emergency area.", "SUPPORTED_PARAPHRASE", "Paraphrases the stated purpose of multiple routes."),
        ("Multiple routes guarantee that every responder arrives within five minutes.", "MODALITY_OVERSTATEMENT", "Reliable access is supported; guaranteed response time is not."),
        ("A single narrow route is preferred because responder access is not important during an industrial emergency.", "CONTRADICTION", "The evidence calls for wide roads and multiple routes for access and escape."),
    ),
    "Q021": (
        ("Officials should evacuate threatened people before impact when warning indicators show danger, and may also evacuate after flooding.", "SUPPORTED_PARAPHRASE", "Preserves both timing conditions stated in the evidence."),
        ("Officials must evacuate every resident exactly twelve hours before any forecast rainfall.", "TIMING_ADDITION", "Precautionary evacuation is supported, but the universal twelve-hour rule is absent."),
        ("Evacuation should begin only after all flood water has receded.", "CONTRADICTION", "The evidence supports evacuation before impact and, when necessary, after inundation."),
    ),
    "Q022": (
        ("Successful evacuation requires dialogue among warning, transport, health, supply, civil-society, NGO, and community stakeholders.", "SUPPORTED_PARAPHRASE", "Condenses the stakeholder list without broadening it."),
        ("Only police and military agencies should coordinate community evacuation.", "ACTOR_MISMATCH", "The passage requires a much broader stakeholder dialogue."),
        ("Communities and transport authorities should be excluded from evacuation coordination.", "CONTRADICTION", "Both are explicitly included."),
    ),
    "Q023": (
        ("A disability-friendly route should, where feasible, connect public transport stops, public facilities, and homes within the shelter site.", "SUPPORTED_PARAPHRASE", "Paraphrases the route's connections and feasibility qualifier."),
        ("Every shelter must build a completely separate disability route that never overlaps the public route.", "MODALITY_OVERSTATEMENT", "The evidence says ideally at least one route, preferably coinciding with the public route."),
        ("Accessible shelter routes need connect only administrative offices, not homes or transport stops.", "SAME_TOPIC_WRONG_CLAIM", "This substitutes different endpoints for those listed."),
    ),
    "Q025": (
        ("Temporary shelter response includes emergency shelters for urgent short-term protection and intermediate shelters for the period before permanent homes are rebuilt.", "SUPPORTED_PARAPHRASE", "Accurately states the two shelter types and their roles."),
        ("Temporary shelters are limited to emergency shelters used for no more than seventy-two hours.", "SCOPE_OVERSTATEMENT", "The evidence also includes intermediate shelters and gives no 72-hour limit."),
        ("Permanent housing is classified as the first type of temporary shelter.", "SAME_TOPIC_WRONG_CLAIM", "The two temporary types are emergency and intermediate shelters."),
    ),
    "Q026": (
        ("Emergency shelters meet immediate short-term protection needs, while intermediate shelters serve mid-term needs until permanent housing is restored.", "SUPPORTED_PARAPHRASE", "Paraphrases the temporal distinction."),
        ("Intermediate shelters must replace permanent housing for at least ten years.", "TIMING_ADDITION", "Intermediate use is supported only until permanent homes are rebuilt; ten years is absent."),
        ("Emergency shelters are intended for the mid-term period after permanent homes are rebuilt.", "CONTRADICTION", "This reverses the emergency/intermediate sequence."),
    ),
    "Q028": (
        ("Temporary shelter sites should have continuous access to water, hygienic sanitation, toilets, electricity, and transportation.", "SUPPORTED_PARAPHRASE", "Restates the listed basic services."),
        ("Every temporary shelter must provide uninterrupted internet and air conditioning to each family.", "UNSUPPORTED_ADDITION", "The listed basic services are supported, but these additions are absent."),
        ("Temporary shelter sites do not need water or sanitation when transport is available.", "CONTRADICTION", "Water and sanitation are explicitly required alongside transportation."),
    ),
    "Q029": (
        ("Shelter support should progress from immediate emergency protection to intermediate accommodation until permanent homes are rebuilt.", "SUPPORTED_PARAPHRASE", "Restates the incremental shelter-response sequence."),
        ("Every family must move from emergency to intermediate shelter after exactly fourteen days.", "TIMING_ADDITION", "The progression is supported, but no universal fourteen-day deadline is given."),
        ("Families should remain indefinitely in emergency shelters instead of progressing toward permanent housing.", "CONTRADICTION", "The evidence frames emergency shelter as short term and intermediate shelter as transitional."),
    ),
    "Q030": (
        ("Authorities should establish a way to identify all genuinely affected families rather than relying only on incomplete existing beneficiary lists.", "SUPPORTED_PARAPHRASE", "Paraphrases the identified exclusion risk and response."),
        ("Only registered property owners may receive aid, even when vulnerable tenants are genuinely affected.", "POPULATION_MISMATCH", "The passage warns that existing lists may omit tenants and other vulnerable groups."),
        ("Pre-existing village lists always contain every affected landless and tenant household.", "CONTRADICTION", "The evidence says those lists may be incomplete."),
    ),
    "Q031": (
        ("Emergency shelter is for urgent short-term protection and should transition to intermediate shelter while permanent housing is restored.", "SUPPORTED_PARAPHRASE", "Uses the evidence's incremental sequence to explain why emergency accommodation is not indefinite."),
        ("Emergency shelters become unsafe automatically after exactly thirty days.", "TIMING_ADDITION", "Short-term use is supported; an automatic 30-day safety threshold is not."),
        ("Emergency accommodation is designed to serve as permanent reconstructed housing.", "CONTRADICTION", "The evidence distinguishes emergency shelter from permanent reconstruction."),
    ),
    "Q033": (
        ("Temporary shelters should be kept a safe distance from damaged or vulnerable structures so a collapse does not endanger occupants.", "SUPPORTED_PARAPHRASE", "Paraphrases the safety-layout instruction available in the selected chunk."),
        ("All temporary shelters must be exactly one kilometre from every existing structure.", "NUMERIC_ADDITION", "Safe distance is supported, but the fixed distance and scope are not."),
        ("Temporary shelters should be attached to damaged structures to simplify construction.", "CONTRADICTION", "This reverses the safe-distance requirement."),
    ),
    "Q034": (
        ("When shelter services are disrupted or critically deficient, authorities should provide alternatives while repairing infrastructure to restore service.", "SUPPORTED_PARAPHRASE", "Restates the simultaneous alternate-arrangement and repair response."),
        ("Disrupted services must be restored within two hours exclusively by private charities.", "ACTOR_MISMATCH", "Restoration is supported, but the deadline and exclusive actor are not."),
        ("Authorities should wait for repairs to finish and provide no temporary service alternatives.", "CONTRADICTION", "The passage expressly requires alternate arrangements during repair."),
    ),
    "Q035": (
        ("Temporary-shelter site selection should consider future hazards, surroundings, geography, soil, access, services, resources, and livelihoods.", "SUPPORTED_PARAPHRASE", "Condenses the factors named in the passage."),
        ("A site is safe whenever it is close to a highway, regardless of soil or future disaster risk.", "CONDITION_ADDITION", "Highway proximity is made a sufficient condition while required considerations are discarded."),
        ("Future disaster vulnerability and soil conditions should be ignored when choosing temporary-shelter sites.", "CONTRADICTION", "Both are explicitly relevant to site selection."),
    ),
    "Q037": (
        ("Inclusive disaster-risk management gives specific attention to gender vulnerabilities, Scheduled Castes and Tribes, older people, children, and persons with disabilities.", "SUPPORTED_PARAPHRASE", "Faithfully paraphrases the enumerated groups."),
        ("Inclusive disaster planning needs special measures only for children and no other group.", "SCOPE_OVERSTATEMENT", "The evidence identifies several groups, not children alone."),
        ("Inclusive disaster-risk management excludes persons with disabilities from its social-inclusion focus.", "CONTRADICTION", "Persons with disabilities are explicitly included."),
    ),
    "Q039": (
        ("Neighbourhood buddy systems and community training can help persons with disabilities obtain emergency assistance.", "SUPPORTED_PARAPHRASE", "Paraphrases the local support measures."),
        ("Each person with a disability must rely on exactly one government-appointed neighbour.", "NUMERIC_ADDITION", "Buddy support is grounded, but the exact number and appointing actor conflict with the passage's flexible approach."),
        ("People with disabilities should be separated from neighbourhood support during emergencies.", "CONTRADICTION", "The evidence promotes local community support and multiple buddies."),
    ),
    "Q040": (
        ("Women-headed households, single women, and widows may face difficulty obtaining recovery information and financial assistance.", "SUPPORTED_PARAPHRASE", "Directly restates the documented access barrier."),
        ("All post-disaster housing grants must be paid only to married male household heads.", "POPULATION_MISMATCH", "The evidence highlights barriers faced by women; it does not prescribe exclusionary eligibility."),
        ("Widows and single women consistently have easier access to reconstruction finance than other survivors.", "CONTRADICTION", "The passage says these groups find access difficult."),
    ),
    "Q041": (
        ("Treating survivors as a uniform group can overlook existing inequalities and produce unequal disaster outcomes.", "SUPPORTED_PARAPHRASE", "Paraphrases the passage's critique of homogeneous treatment."),
        ("Every demographic group experiences identical disaster impacts whenever the same hazard occurs.", "SCOPE_OVERSTATEMENT", "The passage says existing conditions can produce dissimilar outcomes."),
        ("Disaster management becomes fairer when it ignores gender, caste, and class inequities.", "CONTRADICTION", "The evidence says blindness to inequity can make management unfair."),
    ),
    "Q043": (
        ("Stigma, discrimination, and institutional neglect can restrict sexual and gender minorities' access to disaster resources and programmes.", "SUPPORTED_PARAPHRASE", "Restates the barriers described in the evidence."),
        ("All transgender people are legally barred from every disaster-response service.", "SCOPE_OVERSTATEMENT", "The passage describes disadvantage and exclusion, not this universal legal prohibition."),
        ("Disaster frameworks already address every need of sexual and gender minorities without gaps.", "CONTRADICTION", "The evidence says frameworks are usually silent and needs are often overlooked."),
    ),
    "Q044": (
        ("Existing local beneficiary lists may miss landless, SC/ST, socially excluded, women-headed, squatter, and tenant households.", "SUPPORTED_PARAPHRASE", "Paraphrases the populations explicitly identified as potentially omitted."),
        ("Only salaried homeowners are at risk of being absent from village beneficiary lists.", "POPULATION_MISMATCH", "This substitutes a population not identified and excludes those named."),
        ("Pre-existing beneficiary lists are guaranteed to include all vulnerable households.", "CONTRADICTION", "The passage warns the lists may not be complete."),
    ),
    "Q045": (
        ("Intermediate-shelter layouts should avoid dark or isolated blind spots and be safe and accessible for women, older people, children, and persons with disabilities.", "SUPPORTED_PARAPHRASE", "Restates the safety, privacy, and accessibility guidance."),
        ("Only women require privacy and safety consideration in shelter layouts.", "POPULATION_MISMATCH", "The evidence applies safety and privacy to all community members and names several groups."),
        ("Shelter planners should create dark, deserted blind spots to separate vulnerable residents.", "CONTRADICTION", "The passage explicitly says to avoid such spaces."),
    ),
    "Q046": (
        ("A disability-friendly site route should connect transport stops, public facilities, and residential units as far as feasible.", "SUPPORTED_PARAPHRASE", "Paraphrases the listed route connections."),
        ("The route must connect only parking areas and management offices.", "SCOPE_OVERSTATEMENT", "The narrowed endpoints omit the facilities and homes named in the evidence."),
        ("A disability-friendly route should avoid public facilities and residential units.", "CONTRADICTION", "This reverses the required connections."),
    ),
    "Q048": (
        ("Local response teams can help government identify vulnerable people who may require special assistance after floods.", "SUPPORTED_PARAPHRASE", "Restates the role assigned to the teams."),
        ("Only national military units may identify people needing evacuation assistance.", "ACTOR_MISMATCH", "The evidence describes local teams assisting government, not an exclusive military role."),
        ("Response teams should not identify vulnerable residents who need special help.", "CONTRADICTION", "The passage explicitly assigns them that task."),
    ),
    "Q049": (
        ("Regional stores should stock tents, tarpaulins, and other temporary-shelter materials.", "SUPPORTED_PARAPHRASE", "Paraphrases the stockpiling instruction."),
        ("Every regional store must hold exactly 10,000 tents and replace them monthly.", "NUMERIC_ADDITION", "The material type is grounded, but the quantity and schedule are invented."),
        ("Regional emergency stores should stock food only and exclude tents and tarpaulins.", "CONTRADICTION", "The passage explicitly names tents and tarpaulins."),
    ),
    "Q050": (
        ("Regional logistics facilities should coordinate with corresponding NDRF units and maintain temporary shelters, tents, and other non-food stocks.", "SUPPORTED_PARAPHRASE", "Restates the facilities' coordination and stocking roles."),
        ("A single regional facility must supply the entire country without coordination with NDRF.", "SCOPE_OVERSTATEMENT", "This replaces the multi-region coordinated design with an unsupported arrangement."),
        ("Regional logistics facilities are intended to dispose of temporary-shelter stocks before disasters.", "SAME_TOPIC_WRONG_CLAIM", "The stated role is to maintain such stocks."),
    ),
    "Q051": (
        ("Post-disaster transport recovery should rapidly restore roads, highways, public transport, and train services needed for response and supplies.", "SUPPORTED_PARAPHRASE", "Summarises the transport restoration actions in the chunk."),
        ("Every damaged road and rail service must reopen within six hours of a disaster.", "TIMING_ADDITION", "Rapid restoration is supported, but the universal six-hour deadline is absent."),
        ("Recovery plans should delay road and rail restoration until all relief operations are complete.", "CONTRADICTION", "The evidence connects quick restoration to timely response and recovery."),
    ),
    "Q054": (
        ("If site infrastructure is damaged, it should be restored as a priority while additional arrangements maintain required services.", "SUPPORTED_PARAPHRASE", "Paraphrases the continuity instruction."),
        ("Damaged infrastructure must be replaced permanently before any temporary service is offered.", "MODALITY_OVERSTATEMENT", "The evidence permits additional arrangements during restoration, not this sequence."),
        ("Shelter services should stop completely until damaged infrastructure is repaired.", "CONTRADICTION", "The passage calls for additional arrangements in the interim."),
    ),
    "Q055": (
        ("Wide roads and multiple routes allow first responders quick access and provide escape pathways in industrial areas.", "SUPPORTED_PARAPHRASE", "Restates both purposes of the route provision."),
        ("Multiple routes eliminate every possibility of delay or blockage during an industrial accident.", "MODALITY_OVERSTATEMENT", "The passage supports improved access and escape, not a guarantee."),
        ("Industrial emergency planning should remove escape routes to keep responders in one corridor.", "CONTRADICTION", "The evidence requires multiple access and escape routes."),
    ),
    "Q056": (
        ("State and district authorities should establish mechanisms to receive and make effective use of outside emergency assistance.", "SUPPORTED_PARAPHRASE", "Paraphrases the assigned coordination responsibility."),
        ("All outside assistance must be accepted automatically by village councils within one hour.", "ACTOR_MISMATCH", "The actor, automatic acceptance, and deadline are not established."),
        ("Authorities should reject outside organizations' assistance without assessing how it could support response.", "CONTRADICTION", "The passage calls for mechanisms to receive and optimally use such assistance."),
    ),
    "Q057": (
        ("District planners should identify reliable road, rail, and communication networks connecting relief and supply centres with flood-prone areas.", "SUPPORTED_PARAPHRASE", "Restates the preparedness action."),
        ("Only mobile-phone links need verification before relief supplies are required.", "SCOPE_OVERSTATEMENT", "The evidence also identifies road and rail connections."),
        ("Transport links between supply centres and flood-prone areas need not be identified in advance.", "CONTRADICTION", "The passage explicitly calls for their identification."),
    ),
    "Q058": (
        ("Transport and food-supply agencies should coordinate logistics so essential supplies can reach disaster-affected areas.", "SUPPORTED_PARAPHRASE", "Paraphrases the supply availability and transport coordination responsibilities."),
        ("Private airlines alone must deliver every essential item directly to each household.", "ACTOR_MISMATCH", "The evidence describes public logistics coordination and strategic transport, not this exclusive actor or scope."),
        ("Transport agencies should withhold essential supplies from disaster-affected areas during recovery.", "CONTRADICTION", "The evidence seeks adequate supplies and transport to affected areas."),
    ),
    "Q060": (
        ("A dedicated local team should receive temporary-shelter supplies and coordinate distribution to avoid duplicated effort.", "SUPPORTED_PARAPHRASE", "Restates the local receiving and anti-duplication provisions."),
        ("Each NGO should distribute shelter materials independently without consulting local authorities.", "ACTOR_MISMATCH", "The evidence requires coordination with district, block, or village authorities."),
        ("Local teams should order duplicate shelter shipments to increase competition among suppliers.", "CONTRADICTION", "The passage explicitly calls for avoiding duplication."),
    ),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def canonical_bytes(records: Sequence[Mapping[str, object]]) -> bytes:
    rows = []
    for record in sorted(records, key=lambda row: str(row["claim_pair_id"])):
        rows.append(json.dumps([record[field] for field in CANONICAL_FIELDS], ensure_ascii=False, separators=(",", ":")))
    return ("\n".join(rows) + "\n").encode("utf-8")


def challenge_fingerprint(records: Sequence[Mapping[str, object]]) -> str:
    return hashlib.sha256(canonical_bytes(records)).hexdigest()


def _short_excerpt(text: str, limit: int = 220) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit].rsplit(" ", 1)[0] + "…"


def build_artifacts() -> tuple[list[dict[str, object]], dict[str, object], dict[str, object], str]:
    questions = {row["question_id"]: row for row in read_csv(QUESTIONS_PATH)}
    labels = read_csv(LABELS_PATH)
    if len(questions) != 45 or set(questions) != set(CLAIMS):
        raise ValueError("claim constructions must cover the exact 45 retained questions")
    if any(row["benchmark_version"] != SOURCE_BENCHMARK_VERSION for row in labels):
        raise ValueError("source benchmark version changed")
    selected = {
        question_id: min(
            row["chunk_id"] for row in labels
            if row["question_id"] == question_id and row["ai_relevance_grade"] == "2"
        )
        for question_id in questions
    }
    prepared = prepare_corpus()
    label_by_pair = {(row["question_id"], row["chunk_id"]): row for row in labels}
    records: list[dict[str, object]] = []
    evidence_by_question = {}
    for question_id in sorted(questions):
        question = questions[question_id]
        chunk_id = selected[question_id]
        label = label_by_pair[(question_id, chunk_id)]
        if label["ai_relevance_grade"] != "2":
            raise AssertionError("selected evidence is not frozen grade 2")
        evidence = get_chunk_by_id(
            chunk_id, prepared, source_id=label["source_id"], filename=label["filename"],
            page=int(label["page"]), passage_sha256=label["source_passage_sha256"],
        )
        evidence_by_question[question_id] = evidence
        for index, construction_label in enumerate(LABELS):
            claim, subtype, reason = CLAIMS[question_id][index]
            record = {
                "claim_pair_id": f"{question_id}-C{index + 1:02d}",
                "question_id": question_id,
                "effective_question": question["question"],
                "chunk_id": evidence.chunk_id,
                "source_id": evidence.source_id,
                "filename": evidence.filename,
                "page": evidence.page,
                "passage_sha256": evidence.passage_sha256,
                "claim": claim,
                "construction_label": construction_label,
                "construction_reason": reason,
                "reason_subtype": subtype,
                "synthetic_variant": True,
                "not_authoritative_policy": True,
                "benchmark_version": BENCHMARK_VERSION,
                "construction_protocol_version": CONSTRUCTION_PROTOCOL_VERSION,
            }
            records.append(record)
    fingerprint = challenge_fingerprint(records)
    label_counts = Counter(str(row["construction_label"]) for row in records)
    subtype_counts = Counter(str(row["reason_subtype"]) for row in records)
    source_base_counts = Counter(evidence.source_id for evidence in evidence_by_question.values())
    source_pair_counts = Counter(str(row["source_id"]) for row in records)
    topic_counts = Counter(row["topic"] for row in questions.values())
    style_counts = Counter(row["query_style"] for row in questions.values())
    manifest: dict[str, object] = {
        "benchmark_version": BENCHMARK_VERSION,
        "construction_protocol_version": CONSTRUCTION_PROTOCOL_VERSION,
        "source_benchmark_version": SOURCE_BENCHMARK_VERSION,
        "source_label_fingerprint": SOURCE_LABEL_FINGERPRINT,
        "corpus_version": CORPUS_VERSION,
        "corpus_fingerprint": CORPUS_FINGERPRINT,
        "questions": 45,
        "base_evidence_passages": 45,
        "unique_base_chunk_ids": len(set(selected.values())),
        "claim_pairs": 135,
        "label_counts": dict(sorted(label_counts.items())),
        "reason_subtype_counts": {key: subtype_counts.get(key, 0) for key in REASON_SUBTYPES},
        "source_counts": {
            "base_evidence_passages": dict(sorted(source_base_counts.items())),
            "claim_pairs": dict(sorted(source_pair_counts.items())),
        },
        "topic_counts": dict(sorted(topic_counts.items())),
        "query_style_counts": dict(sorted(style_counts.items())),
        "challenge_fingerprint": fingerprint,
        "fingerprint_procedure": {
            "canonical_fields_in_order": list(CANONICAL_FIELDS),
            "record_order": "claim_pair_id ascending (Unicode code-point order)",
            "record_encoding": "compact UTF-8 JSON array; ensure_ascii=false",
            "separator": "LF between records and one final LF",
            "hash": "SHA-256",
        },
        "evaluation_order": {
            "rule": "ascending SHA-256(claim_pair_id + challenge_fingerprint), then claim_pair_id",
            "claim_pair_ids": label_independent_order([str(row["claim_pair_id"]) for row in records], fingerprint),
        },
        "provenance": {
            "independently_human_gold": False,
            "construction_labeled": True,
            "ai_assisted_construction": True,
            "authoritative_evidence": True,
            "note": "Claims were constructed with AI assistance from frozen grade-2 evidence; labels follow controlled construction and are not independent expert annotations.",
        },
        "official_phase14b_metrics_calculated": False,
    }
    spot_records = []
    for label in LABELS:
        candidates = [row for row in records if row["construction_label"] == label]
        candidates.sort(key=lambda row: hashlib.sha256(f"{row['claim_pair_id']}|{fingerprint}".encode()).hexdigest())
        spot_records.extend(candidates[:5])
    spotcheck = {
        "benchmark_version": BENCHMARK_VERSION,
        "challenge_fingerprint": fingerprint,
        "purpose": "deterministic inspection sample; not human-reviewed status",
        "sample_rule": "five per class by ascending SHA-256(claim_pair_id + '|' + challenge_fingerprint)",
        "label_counts": dict(Counter(row["construction_label"] for row in spot_records)),
        "examples": spot_records,
    }
    review_lines = [
        "# Sentinel-Agent V3 — Claim-Support Challenge Review", "",
        "> Construction-labeled, AI-assisted audit material. This is not an independently human-reviewed or expert-gold benchmark. Evidence excerpts are short local reconstructions from authoritative PDFs; constructed claims are not authoritative policy.", "",
        f"Benchmark: `{BENCHMARK_VERSION}`", f"Fingerprint: `{fingerprint}`", "",
    ]
    for record in records:
        evidence = evidence_by_question[str(record["question_id"])]
        review_lines.extend([
            f"## {record['claim_pair_id']}", "",
            "**SYNTHETIC CHALLENGE CLAIM — NOT AUTHORITATIVE POLICY**" if record["construction_label"] != "SUPPORTED" else "**CONSTRUCTED PARAPHRASE — NOT AUTHORITATIVE POLICY WORDING**", "",
            f"- Question ID: `{record['question_id']}`",
            f"- Question: {record['effective_question']}",
            f"- Claim: {record['claim']}",
            f"- Construction label: `{record['construction_label']}`",
            f"- Reason subtype: `{record['reason_subtype']}`",
            f"- Construction reason: {record['construction_reason']}",
            f"- Source: `{record['filename']}`",
            f"- PDF page: `{record['page']}`",
            f"- Chunk ID: `{record['chunk_id']}`", "",
            f"> Evidence excerpt: {_short_excerpt(evidence.text)}", "",
        ])
    return records, manifest, spotcheck, "\n".join(review_lines).rstrip() + "\n"


def duplicate_audit(records: Sequence[Mapping[str, object]], evidence_text: Mapping[str, str]) -> dict[str, object]:
    claims = [str(row["claim"]) for row in records]
    normalized = [re.sub(r"[^a-z0-9]+", " ", claim.casefold()).strip() for claim in claims]
    exact = len(claims) - len(set(claims))
    normalized_duplicates = len(normalized) - len(set(normalized))
    suspicious = []
    for row in records:
        if row["construction_label"] != "SUPPORTED":
            continue
        claim = " ".join(str(row["claim"]).casefold().split())
        evidence = " ".join(evidence_text[str(row["question_id"])].casefold().split())
        if claim in evidence:
            suspicious.append(row["claim_pair_id"])
    return {
        "exact_duplicate_claims": exact,
        "normalized_duplicate_claims": normalized_duplicates,
        "suspicious_supported_exact_copies": suspicious,
    }


def main() -> int:
    records, manifest, spotcheck, review = build_artifacts()
    PHASE14.mkdir(parents=True, exist_ok=True)
    CHALLENGE_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    SPOTCHECK_PATH.write_text(json.dumps(spotcheck, indent=2, ensure_ascii=False) + "\n")
    REVIEW_PATH.write_text(review)
    print(f"questions={manifest['questions']} base_evidence={manifest['base_evidence_passages']} pairs={manifest['claim_pairs']}")
    print(f"labels={manifest['label_counts']}")
    print(f"fingerprint={manifest['challenge_fingerprint']}")
    print("official_phase14b_metrics_calculated=False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
