#!/usr/bin/env python3
"""Build the Phase 14D construction-labeled claim-support challenge sets (Lead).

Spec: specs/V4_CLAIM_SUPPORT_14D_SPEC.md §3. Writes data/eval_v4/phase14d/{challenge_test.json,
challenge_practice.json, manifest.json, selection_log.json}. Deterministic: rerunning reproduces the same bytes.
Claims are controlled benchmark constructions, not authoritative guidance; negative claims must never be
presented as NDMA guidance. No model output was used to write or check them.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rag.ingest import prepare_corpus  # noqa: E402

OUT = ROOT / "data/eval_v4/phase14d"
V3_CHALLENGE = ROOT / "data/eval_v3/phase14/claim_support_challenge.json"
CHALLENGE_ID = "v4-claim-support-challenge-14d-v1"
CONSTRUCTION_PROTOCOL = "v4-claim-support-construction-14d-v1"
CORPUS_VERSION = "v3-authoritative-corpus-v1"
CORPUS_FINGERPRINT = "a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753"
LABELS = ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED")
FIELDS = (
    "claim_pair_id", "challenge_set", "chunk_id", "source_id", "filename", "page", "passage_sha256", "claim",
    "construction_label", "construction_reason", "reason_subtype", "synthetic_variant", "not_authoritative_policy",
    "benchmark_version", "construction_protocol_version",
)
SELECTION_RULE = (
    "Exclude every chunk whose (source_id, page) holds a V3 challenge chunk and every chunk shorter than 400 "
    "characters; walk the rest in ascending SHA-256('14d-v1:' + chunk_id) order; skip NON_SUBSTANTIVE, "
    "GARBLED_TEXT or NEAR_DUPLICATE (>= 80% of the chunk's word set in an accepted chunk); first 45 accepted = "
    "test, next 10 = practice."
)
MIX = {
    "test": {
        "PARTIALLY_SUPPORTED": {"SCOPE_OVERSTATEMENT": 10, "TIMING_ADDITION": 8, "NUMERIC_ADDITION": 7,
                                "ACTOR_MISMATCH": 7, "MODALITY_OVERSTATEMENT": 5, "POPULATION_MISMATCH": 4,
                                "UNSUPPORTED_ADDITION": 3, "CONDITION_ADDITION": 1},
        "UNSUPPORTED": {"CONTRADICTION": 40, "SAME_TOPIC_WRONG_CLAIM": 5},
    },
    "practice": {
        "PARTIALLY_SUPPORTED": {"SCOPE_OVERSTATEMENT": 2, "TIMING_ADDITION": 2, "NUMERIC_ADDITION": 2,
                                "ACTOR_MISMATCH": 2, "MODALITY_OVERSTATEMENT": 1, "POPULATION_MISMATCH": 1},
        "UNSUPPORTED": {"CONTRADICTION": 9, "SAME_TOPIC_WRONG_CLAIM": 1},
    },
}

# Judgement skips (every other walked chunk is accepted unless it is an automatic NEAR_DUPLICATE).
# NON_SUBSTANTIVE here is responsibility-matrix / data-table residue, abbreviation lists or acknowledgements.
SKIPS = {
    "ndma-national-disaster-management-plan-2019-p212-c1": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p280-c1": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p162-c0": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p179-c0": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p204-c0": "NON_SUBSTANTIVE",
    "ndma-flood-guidelines-2008-p121-c0": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p216-c0": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p144-c0": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p289-c1": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p246-c0": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p290-c0": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p137-c0": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p344-c1": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p272-c2": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p278-c0": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p29-c0": "NON_SUBSTANTIVE",
    "ndma-temporary-shelters-2019-p13-c0": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p183-c1": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p27-c0": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p254-c1": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p211-c0": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p320-c2": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p156-c1": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p151-c1": "NON_SUBSTANTIVE",
    "ndma-national-disaster-management-plan-2019-p196-c0": "NON_SUBSTANTIVE",
}

# chunk_id -> ((supported claim, reason), (partial claim, subtype, reason), (unsupported claim, subtype, reason)),
# in acceptance order: the first 45 are the test set, the last 10 the practice set.
CLAIMS: dict[str, tuple[tuple[str, str], tuple[str, str, str], tuple[str, str, str]]] = {
    # ---------------- test set ----------------
    "ndma-national-disaster-management-plan-2019-p335-c1": (
        ("Domestic on-budget sources of recovery funding usually include government operational and capital budgets and special levies or surcharges for recovery.", "Paraphrases two of the listed domestic funding sources."),
        ("Recovery funding comes entirely from domestic on-budget sources such as government budgets and special recovery levies.", "SCOPE_OVERSTATEMENT", "Domestic sources are listed, but 'entirely' is not established; the passage also mentions contracting with funding agencies."),
        ("The plan rules out issuing sovereign reconstruction bonds as a source of recovery funds.", "CONTRADICTION", "Issuing sovereign reconstruction or development bonds is listed as a source."),
    ),
    "ndma-national-disaster-management-plan-2019-p99-c2": (
        ("The Paris Agreement entered into force on 4 November 2016, after at least 55 Parties covering an estimated 55% of global emissions had deposited their instruments.", "Restates the entry-into-force condition and date."),
        ("The agreement provides for a global stock-take every five years, with the first stock-take required in 2018.", "TIMING_ADDITION", "The five-yearly stock-take is stated; a first stock-take in 2018 is not."),
        ("India has not ratified the Paris Agreement and has not submitted an NDC.", "CONTRADICTION", "The passage says India ratified the agreement and submitted its NDC."),
    ),
    "ndma-national-disaster-management-plan-2019-p349-c3": (
        ("Under Section 39 (b), State Government departments may integrate disaster prevention and mitigation measures into their development plans and projects.", "Paraphrases Section 39 (b) as quoted."),
        ("Section 38 (2) (f) requires every State Government to integrate vulnerability-reduction measures into the State development plan.", "MODALITY_OVERSTATEMENT", "The passage says the State Government 'may integrate'; 'requires' turns permission into a mandate."),
        ("Section 38 (2) (e) prohibits State departments from including mitigation measures in their development plans.", "CONTRADICTION", "Section 38 (2) (e) provides for ensuring such integration."),
    ),
    "ndma-flood-guidelines-2008-p113-c2": (
        ("Flood shelters are to be used for purposes such as running schools or anganwadis so that they are properly maintained and in good condition during floods.", "Paraphrases the shelter-use and maintenance provision."),
        ("State governments will ensure flood shelters are used for schools and anganwadis, with the National Disaster Response Force responsible for their upkeep.", "ACTOR_MISMATCH", "Use through state, district and local authorities is supported; an NDRF upkeep role is added."),
        ("Flood shelters should be kept unused between floods so that they remain in good condition.", "CONTRADICTION", "The passage promotes using shelters for schools and other facilities to keep them maintained."),
    ),
    "ndma-national-disaster-management-plan-2019-p340-c1": (
        ("The national policy treats capacity development as a continuous process that must cope with staff turnover, new recruits and technical change.", "Paraphrases the continuous-process challenges."),
        ("Capacity development must address staff turnover and new recruits, and every agency must complete a capacity review within its first year.", "TIMING_ADDITION", "The challenges are stated; a first-year review deadline is invented."),
        ("The NPDM 2009 gives the National Institute of Disaster Management only a minor role in capacity development.", "CONTRADICTION", "The policy envisages a pivotal role for NIDM."),
    ),
    "ndma-temporary-shelters-2019-p90-c0": (
        ("CGI roofing sheets are non-combustible, and their corrugations help drain water away from the shelter.", "Restates two listed properties of CGI sheets."),
        ("CGI sheet roofs are lightweight and non-combustible and weigh less than 5 kg per square metre.", "NUMERIC_ADDITION", "Light weight and non-combustibility are stated; the weight figure is invented."),
        ("CGI sheets have low thermal conductivity, so they keep shelters well insulated against outdoor temperatures.", "CONTRADICTION", "The passage lists high thermal conductivity as a limitation."),
    ),
    "ndma-flood-guidelines-2008-p112-c2": (
        ("People are to be made aware of keeping a kit with medicines, a torch, identity and ration cards and non-perishable food ready before the monsoon starts.", "Paraphrases the special-kit awareness measure."),
        ("Specially designed public awareness programmes are to be developed for women, the elderly and migrant workers.", "POPULATION_MISMATCH", "Women and the elderly are named; migrant workers are not."),
        ("Communities should not attempt to make flood rescue devices from household articles.", "CONTRADICTION", "The community is to be trained to make and use improvised rescue devices from household articles."),
    ),
    "ndma-temporary-shelters-2019-p47-c2": (
        ("Where a temporary shelter needs a foundation, it should preferably be at least 300 mm deep, with variations depending on soil and site conditions.", "Restates the foundation-depth guidance."),
        ("The plinth of every temporary shelter must be at least 150 mm above the highest expected flood level, with no exceptions.", "MODALITY_OVERSTATEMENT", "The passage says 'should preferably'; a strict mandate with no exceptions is not stated."),
        ("On soils with low bearing capacity, heavy structures should be built to stay stable.", "CONTRADICTION", "Light weight structures are recommended where bearing capacity is low."),
    ),
    "ndma-flood-guidelines-2008-p78-c0": (
        ("Flood plain zoning cannot remedy existing situations, but it helps minimise flood damage in new developments.", "Paraphrases the stated limit and benefit of zoning."),
        ("Flood plain zoning bans all development activity throughout both protected and unprotected flood plain areas.", "SCOPE_OVERSTATEMENT", "Zoning limits development in both areas; protected areas still allow low-damage activities."),
        ("In protected areas, flood plain zoning allows any development regardless of the damage it would suffer if protection failed.", "CONTRADICTION", "Only activities that would not involve heavy damage if protection fails are allowed."),
    ),
    "ndma-national-disaster-management-plan-2019-p50-c0": (
        ("The DM Act has no provision for declaring a disaster a 'national calamity', and state governments usually lead disaster management with central support.", "Paraphrases the national-calamity point and the supporting central role."),
        ("Central agencies generally take part on the state government's request, provided the disaster affects more than one district.", "CONDITION_ADDITION", "Participation on request is stated; the multi-district condition is invented."),
        ("Under the DM Act, the central government formally notifies major events as national disasters and takes over their management.", "CONTRADICTION", "The Act has no provision for notifying a national disaster; states usually lead."),
    ),
    "ndma-flood-guidelines-2008-p135-c1": (
        ("States were recommended to legislate against unauthorised riverbed cultivation and encroachment into drains, and to strengthen enforcement where such laws exist.", "Paraphrases Recommendation 14."),
        ("States should legislate against unauthorised riverbed cultivation, with the Central Water Commission enforcing these laws.", "ACTOR_MISMATCH", "State legislation is supported; a CWC enforcement role is added."),
        ("The recommendation bans all cultivation in riverbeds, including crops such as watermelons.", "CONTRADICTION", "Crops like watermelons may be allowed with caution."),
    ),
    "ndma-flood-guidelines-2008-p21-c2": (
        ("One objective of the guidelines is to build flood-resistant features into new structures in flood-prone areas.", "Restates objective 4."),
        ("The guidelines aim to make all existing and new buildings in flood-prone areas flood resistant.", "SCOPE_OVERSTATEMENT", "New structures are covered; all existing buildings are not."),
        ("The guidelines shift the focus away from preparedness toward post-flood relief.", "CONTRADICTION", "Objective 1 shifts the focus to preparedness."),
    ),
    "ndma-temporary-shelters-2019-p22-c2": (
        ("Permanent housing reconstruction often takes two to three years, so affected families need durable intermediate shelters in the meantime.", "Paraphrases the rationale for intermediate shelters."),
        ("Relief camps in existing public buildings are set up immediately and must be vacated within two weeks.", "TIMING_ADDITION", "Relief camps in public buildings are described; a two-week vacating deadline is not."),
        ("Permanent housing reconstruction is usually completed within six months of a disaster.", "SAME_TOPIC_WRONG_CLAIM", "The passage says it often takes 2-3 years."),
    ),
    "ndma-flood-guidelines-2008-p43-c3": (
        ("The flood management guidelines stress preparedness, prevention and mitigation before floods, and prompt response, relief and recovery during and after them.", "Paraphrases the stated emphasis."),
        ("The new approach gives equal emphasis to preparedness, prevention, mitigation, response and relief, and gives preparedness the largest share of funding.", "UNSUPPORTED_ADDITION", "Equal emphasis is stated; a funding priority is not."),
        ("The guidelines keep the earlier relief-centric approach to disaster management.", "CONTRADICTION", "The passage describes a shift away from the relief-centric approach."),
    ),
    "ndma-national-disaster-management-plan-2019-p60-c0": (
        ("Storm surge is an abnormal rise of water generated by a storm above the predicted astronomical tide, and it causes many of the deaths in tropical cyclones.", "Paraphrases the definition and casualty statement."),
        ("When a storm surge coincides with high tide, storm tides can reach 6 metres or more, and they occur on average twice a year on the east coast.", "NUMERIC_ADDITION", "The 6-metre storm tides are stated; the twice-a-year frequency is invented."),
        ("Floods affect an average of about 40 million hectares in India every year.", "SAME_TOPIC_WRONG_CLAIM", "The yearly average is about 7.5 million hectares; 40 million is the 1980 estimate of the susceptible area."),
    ),
    "ndma-temporary-shelters-2019-p33-c0": (
        ("Rental accommodation in undamaged existing houses is described as an alternative way of providing temporary shelter, particularly in urban areas.", "Paraphrases the rental-accommodation point."),
        ("Temporary shelters fall into three typologies, and rental accommodation is the preferred option in both urban and rural areas.", "SCOPE_OVERSTATEMENT", "Three typologies are stated; rental is noted for urban contexts, not preferred everywhere."),
        ("Assembly-based shelters such as tents and shipping containers are built on site from bricks, stone and cement.", "CONTRADICTION", "Assembly-based shelters are pre-fabricated elements assembled on site; brick and stone are construction-based."),
    ),
    "ndma-flood-guidelines-2008-p51-c3": (
        ("Because rivers such as the Ganga and Brahmaputra originate in neighbouring countries, information from those countries is needed to manage floods.", "Paraphrases the international-information need."),
        ("Several expert bodies called for a central organisation to deal with floods, to be run by the Ministry of External Affairs.", "ACTOR_MISMATCH", "The call for a central organisation is stated; MEA control is invented."),
        ("Expert committees have advised against a basin approach to flood management.", "CONTRADICTION", "The committees highlighted the need for a basin approach."),
    ),
    "ndma-flood-guidelines-2008-p49-c1": (
        ("The Brahmaputra Board was set up by the Government of India as a statutory body under the Brahmaputra Board Act, 1980.", "Restates the Board's statutory origin."),
        ("The MOWR will strengthen the GFCC, completing the work by the end of the Eleventh Five-Year Plan.", "TIMING_ADDITION", "Strengthening the GFCC is stated; the completion deadline is not."),
        ("The 2004 Task Force recommended winding down the Ganga Flood Control Commission.", "CONTRADICTION", "The Task Force recommended strengthening it."),
    ),
    "ndma-flood-guidelines-2008-p59-c3": (
        ("Channel improvement has not been widely used in India, mainly because of high costs and topographical constraints.", "Paraphrases the stated reasons."),
        ("Channel improvement is recommended for entire river lengths to lower flood levels.", "SCOPE_OVERSTATEMENT", "It is recommended for local reaches where required, not entire rivers."),
        ("Studies confirm a general rise in river beds across India.", "CONTRADICTION", "The studies do not confirm the belief in a general rise."),
    ),
    "ndma-national-disaster-management-plan-2019-p66-c3": (
        ("A cloudburst is an extreme amount of precipitation in a short period that can create flood conditions.", "Paraphrases the definition."),
        ("A cloudburst is an extreme amount of rain in a short period, defined as more than 100 mm in one hour.", "NUMERIC_ADDITION", "The definition is supported; the numeric threshold is not in the passage."),
        ("A cloudburst is literally the breaking open of a cloud.", "CONTRADICTION", "The passage says it is not, as sometimes understood, the breaking open of a cloud."),
    ),
    "ndma-national-disaster-management-plan-2019-p42-c2": (
        ("Development that ignores disaster probabilities can worsen existing risks and introduce new ones.", "Paraphrases the mainstreaming rationale."),
        ("Social inclusion in disaster management means not leaving out community members on the basis of age, gender or disability, with priority given to urban residents.", "POPULATION_MISMATCH", "Inclusion across age, gender and disability is stated; an urban priority is invented."),
        ("Mainstreaming DRR means keeping disaster risk reduction separate from development initiatives.", "CONTRADICTION", "Mainstreaming is the integration of DRR into all developmental initiatives."),
    ),
    "ndma-flood-guidelines-2008-p132-c2": (
        ("A task force set up by the Ministry of Water Resources in August 2004 examined recurring floods in Assam, Bihar, West Bengal and eastern Uttar Pradesh.", "Restates the task force's origin and remit."),
        ("The 2004 Task Force on flood management was chaired jointly by the Chairman of the CWC and the Chairman of the NDMA.", "ACTOR_MISMATCH", "The CWC Chairman chaired it; an NDMA co-chair is invented."),
        ("The listed recommendations called for less emphasis on non-structural measures.", "CONTRADICTION", "They call for more emphasis on non-structural measures."),
    ),
    "ndma-temporary-shelters-2019-p79-c1": (
        ("Masonry walls in temporary shelters should not rise above sill level (1200 mm), to limit damage in recurring disasters.", "Paraphrases the wall-height guidance."),
        ("125 mm thick walls are banned by law in temporary shelters.", "MODALITY_OVERSTATEMENT", "Such walls 'should be avoided'; a legal ban is not stated."),
        ("Temporary shelter walls should be built well above sill level to give occupants more protection.", "CONTRADICTION", "Walls should not be taller than sill level."),
    ),
    "ndma-flood-guidelines-2008-p74-c2": (
        ("Diverting part of the floodwater into natural depressions, swamps or lakes can be an economical alternative to dams and reservoirs for flood moderation.", "Paraphrases the natural-detention point."),
        ("Natural depressions near rivers can moderate floods economically and can replace dams and reservoirs everywhere.", "SCOPE_OVERSTATEMENT", "An economical alternative depending on topography is stated; universal replacement is not."),
        ("Water stored in reservoirs during floods may not be used for irrigation, power or drinking water.", "CONTRADICTION", "Stored water is released for irrigation, power generation, drinking and industrial use."),
    ),
    "ndma-flood-guidelines-2008-p116-c0": (
        ("After a flood, a team of a social worker, a psychologist and a psychiatrist is to provide counselling to victims.", "Restates the psychosocial provision."),
        ("Dead bodies are to be disposed of through district authorities after identification, within six hours of recovery.", "TIMING_ADDITION", "Disposal after identification is stated; the six-hour limit is invented."),
        ("Documentation of the medical response after a flood is to be done by the district collector.", "SAME_TOPIC_WRONG_CLAIM", "The passage assigns documentation to a medical administrator."),
    ),
    "ndma-national-disaster-management-plan-2019-p69-c1": (
        ("The WMO defines a heat wave as five or more consecutive days on which the daily maximum temperature exceeds the average maximum by five degrees Celsius.", "Restates the WMO definition."),
        ("The CWC and the IMD jointly monitor 467 glacial lakes and water bodies in the Indian Himalayan Region.", "ACTOR_MISMATCH", "The CWC monitors 467 lakes; joint IMD monitoring is not stated."),
        ("The Lhonak glacier lake shrank from 1.26 km² in 1976 to 0.18 km² by 2013.", "CONTRADICTION", "The lake grew from 0.18 km² to 1.26 km²."),
    ),
    "ndma-temporary-shelters-2019-p47-c0": (
        ("Materials such as stone, bamboo, bricks and wood can be salvaged from debris and reused to build intermediate shelters.", "Paraphrases the salvage-and-reuse point."),
        ("Salvaged debris materials can be reused for every type of shelter, including permanent housing.", "SCOPE_OVERSTATEMENT", "Reuse for intermediate-phase shelters is stated, not for every type including permanent housing."),
        ("Bulldozers should clear rubble from damaged house sites before any salvageable materials are collected.", "CONTRADICTION", "Mechanised clearance should preferably come only after salvageable material is collected."),
    ),
    "ndma-flood-guidelines-2008-p39-c2": (
        ("The IMD and CWC, together with state governments, are to develop forecasting and warning systems for flood-prone areas.", "Restates the forecasting responsibility."),
        ("The IMD and CWC will develop forecasting and warning systems for flood-prone areas, starting with Rajasthan.", "UNSUPPORTED_ADDITION", "The systems are stated; a Rajasthan-first sequence is not."),
        ("Such events have never occurred in Rajasthan, Madhya Pradesh or Uttar Pradesh.", "CONTRADICTION", "The passage says such events have also occurred in these states."),
    ),
    "ndma-national-disaster-management-plan-2019-p33-c1": (
        ("At the district level, the DDMA is the nodal agency for coordinating the response, supported by other agencies.", "Restates the district-level nodal agency."),
        ("The state government activates Incident Response Teams at state, district or block level within one hour of a disaster.", "TIMING_ADDITION", "Activation as required is stated; a one-hour deadline is not."),
        ("Central ministries direct the response on their own initiative, without waiting for any request from the state.", "CONTRADICTION", "Central ministries assist as per request from the State/UT."),
    ),
    "ndma-national-disaster-management-plan-2019-p45-c2": (
        ("The plan describes three recovery periods: early (within eighteen months), medium (within five years) and long-term (within five to ten years).", "Restates the three recovery periods."),
        ("Early recovery is to take place within eighteen months and must restore at least 80 percent of damaged housing.", "NUMERIC_ADDITION", "The eighteen-month period is stated; the 80 percent target is invented."),
        ("The NDMP sets fixed recovery timelines for every type of disaster.", "CONTRADICTION", "The NDMP discusses recovery periods only in general terms without timelines."),
    ),
    "ndma-temporary-shelters-2019-p48-c1": (
        ("Lightweight roofs on temporary shelters should be anchored very well, which is particularly important in cyclone-prone regions.", "Paraphrases the roof-anchoring guidance."),
        ("Strong joinery lets a house sway as one unit in an earthquake, preventing any damage at all.", "SCOPE_OVERSTATEMENT", "Total collapse can be avoided, but the passage says some damage may occur."),
        ("Heavy roofs are recommended for temporary shelters in hazard-prone areas.", "CONTRADICTION", "Preferably no heavy weight roofs should be allowed there."),
    ),
    "ndma-flood-guidelines-2008-p87-c2": (
        ("State governments and SDMAs are to set up websites and portals to share flood-related information with stakeholders.", "Restates the dissemination measure."),
        ("State governments will make flood information available in multiple formats for different stakeholder groups, including tourists visiting flood-prone areas.", "POPULATION_MISMATCH", "Multiple formats for stakeholder groups are stated; tourists are not mentioned."),
        ("Flood risk information is to be kept internal to government agencies rather than shared with stakeholders.", "CONTRADICTION", "The information is to be disseminated to stakeholder groups."),
    ),
    "ndma-national-disaster-management-plan-2019-p349-c1": (
        ("Section 32 (a) provides that every office at the district level shall prepare a plan setting out prevention and mitigation provisions from the District Plan.", "Paraphrases Section 32 (a)."),
        ("Section 30 (2) (xiv) obliges every District Authority to upgrade its early warning mechanism each year.", "MODALITY_OVERSTATEMENT", "The District Authority 'may' set up and upgrade the mechanism; an annual obligation is not stated."),
        ("Section 31 (3) (b) excludes prevention and mitigation measures from the District Plan.", "CONTRADICTION", "It provides that the District Plan shall include such measures."),
    ),
    "ndma-flood-guidelines-2008-p62-c0": (
        ("Road and railway embankments that are not properly aligned and designed can increase an area's vulnerability to flooding and drainage congestion.", "Paraphrases the embankment risk."),
        ("Sea walls and coastal protection works will be planned and executed by coastal states and port authorities under the supervision of the Indian Navy.", "ACTOR_MISMATCH", "Coastal states and port authorities are named; Navy supervision is invented."),
        ("Road and railway embankments reduce drainage congestion wherever they cross drainage lines.", "CONTRADICTION", "Improperly designed embankments may increase drainage congestion."),
    ),
    "ndma-flood-guidelines-2008-p30-c0": (
        ("The guidelines accept that floods cannot be prevented but say they can be managed to minimise loss of life, livelihoods and property.", "Paraphrases the opening premise."),
        ("Flood response has been reactive so far, and the guidelines will make it fully preventive by 2010.", "TIMING_ADDITION", "The reactive past is stated; a 2010 target is invented."),
        ("The guidelines state that floods can be prevented altogether with enough structural works.", "CONTRADICTION", "The guidelines say floods cannot be prevented."),
    ),
    "ndma-flood-guidelines-2008-p155-c2": (
        ("Under the model bill, the Flood Zoning Authority may direct a land owner or occupier to remove an unauthorised obstruction within a specified time.", "Paraphrases Section 24 (1)."),
        ("The Flood Zoning Authority may direct an owner to remove an unauthorised obstruction, which must be done within seven days.", "TIMING_ADDITION", "The time is 'as may be specified'; a fixed seven days is invented."),
        ("The model bill gives the Flood Zoning Authority no power to order the removal of obstructions.", "CONTRADICTION", "Chapter VII grants exactly that power."),
    ),
    "ndma-national-disaster-management-plan-2019-p351-c1": (
        ("The Government of India currently acts as a self-insurer for the National and State Disaster Response Funds.", "Restates the self-insurer position."),
        ("Relief funds are monitored by the MHA in consultation with the Ministry of Finance and the Reserve Bank of India.", "ACTOR_MISMATCH", "MHA with the Ministry of Finance is stated; the RBI is added."),
        ("The Government of India insures the National and State Disaster Response Funds with private insurance companies.", "CONTRADICTION", "The government acts as a self-insurer."),
    ),
    "ndma-national-disaster-management-plan-2019-p56-c1": (
        ("The NDMP is not an omnibus plan with one budget; it is to be financed from union and state budgets through various ministries and agencies.", "Paraphrases the financing approach."),
        ("Every ministry, department and state must prepare a DM plan, and every district and village panchayat must also prepare one under the Act.", "SCOPE_OVERSTATEMENT", "Ministries, departments and states are named; districts and village panchayats are added."),
        ("DRR mainstreaming receives its own separate central budget allocation under the plan.", "CONTRADICTION", "There cannot be a separate financial allocation for it."),
    ),
    "ndma-flood-guidelines-2008-p37-c0": (
        ("The state governments are to ensure that every flood event is properly documented and its damage assessed on a scientific basis.", "Restates the documentation duty."),
        ("The highest number of human lives lost to floods in a year was 11,316, in 1977, against an average of 1,587, and the average has since fallen below 500.", "NUMERIC_ADDITION", "The maximum and average are stated; the later fall below 500 is invented."),
        ("The largest area affected by floods in a single year was recorded in 1998.", "SAME_TOPIC_WRONG_CLAIM", "The maximum area affected was in 1978; 1998 is the year of maximum damages."),
    ),
    "ndma-flood-guidelines-2008-p105-c0": (
        ("A compulsory flood-plain insurance scheme would first be tried in a few selected areas on an experimental basis before any wider roll-out.", "Paraphrases the experimental introduction of the scheme."),
        ("Insurance of structures, buildings and crops in flood plains has been made compulsory.", "MODALITY_OVERSTATEMENT", "The MOWR will explore the possibility; the claim states it as an enacted requirement."),
        ("Insurance premiums in flood-prone areas are to be the same everywhere, regardless of flood risk.", "CONTRADICTION", "Studies are to develop premiums graded according to flood risk."),
    ),
    "ndma-temporary-shelters-2019-p44-c2": (
        ("Communities should receive basic training on using shelter kits, including site preparation, foundations and anchors, and repair over time.", "Paraphrases the training guidance."),
        ("Cash support for hiring labour to assemble shelters is reserved for elderly people.", "POPULATION_MISMATCH", "Cash support for vulnerable people is stated; restricting it to the elderly is not."),
        ("Shelter kits should be distributed without any training for the affected communities.", "CONTRADICTION", "Basic training should be held on using the kits."),
    ),
    "ndma-flood-guidelines-2008-p79-c0": (
        ("In areas liable to flooding in a 25-year flood, residential buildings could be allowed if built on stilts, with minimum plinth levels and no basements.", "Restates the 25-year zone stipulations."),
        ("In the 25-year flood zone, residential buildings could be permitted on stilts at least 3 metres high.", "NUMERIC_ADDITION", "Construction on stilts is stated; the 3-metre height is invented."),
        ("Basements are encouraged for residential buildings in the 25-year flood zone.", "CONTRADICTION", "Basements are prohibited there."),
    ),
    "ndma-national-disaster-management-plan-2019-p340-c0": (
        ("Capacity development for DRR must go beyond human resource development to address organisational and institutional issues.", "Paraphrases the institutional focus."),
        ("Partnerships are integral to institutional capacity building, and all capacity development must be delivered through public-private partnerships.", "SCOPE_OVERSTATEMENT", "Partnerships are integral; delivering all capacity development through PPPs is not stated."),
        ("Capacity development for DRR should focus only on human resource development.", "CONTRADICTION", "It must go beyond human resource development."),
    ),
    "ndma-flood-guidelines-2008-p37-c1": (
        ("An area is waterlogged when the water table rises enough to saturate the soil pores in the crop root zone, restricting the circulation of air.", "Restates the waterlogging definition."),
        ("The Irrigation Commission (1972) estimated the area liable to waterlogging at 48.4 lakh hectares, a figure that doubled by 1990.", "NUMERIC_ADDITION", "The 1972 estimate is stated; the later doubling is invented."),
        ("Over-irrigation cannot cause waterlogging; only surface flooding can.", "CONTRADICTION", "Excess rain and/or over-irrigation are named causes."),
    ),
    "ndma-national-disaster-management-plan-2019-p59-c1": (
        ("Although the North Indian Ocean basin generates only about seven per cent of the world's cyclones, their impact is comparatively high.", "Paraphrases the share-versus-impact point."),
        ("The North Indian Ocean basin generates about seven per cent of the world's cyclones, and the number of cyclones there has doubled since 1990.", "UNSUPPORTED_ADDITION", "The seven per cent share is stated; a doubling since 1990 is not."),
        ("A tropical cyclone has winds of at least 100 knots.", "SAME_TOPIC_WRONG_CLAIM", "The stated threshold is gale force, a minimum of 34 knots."),
    ),
    # ---------------- practice set ----------------
    "ndma-flood-guidelines-2008-p51-c1": (
        ("The MOWR, in close collaboration with the NDMA, will establish a National Flood Management Institute.", "Restates the establishment decision."),
        ("The proposed institute will train police, civil defence and NGO personnel from its first year of operation.", "TIMING_ADDITION", "Such training is for a subsequent phase, not the first year."),
        ("The proposed institute will train only central government engineers and never state personnel.", "CONTRADICTION", "It trains central and state engineers and administrators, and later others."),
    ),
    "ndma-national-disaster-management-plan-2019-p93-c3": (
        ("The Sendai Framework was the first international agreement adopted within the post-2015 development agenda.", "Restates the framework's status."),
        ("The Sendai Framework, the first post-2015 international agreement, was adopted by 187 countries.", "NUMERIC_ADDITION", "Its status is stated; the number of countries is not."),
        ("The Sendai Framework moved global policy away from disaster risk reduction toward post-disaster relief.", "CONTRADICTION", "It marks a shift towards comprehensive disaster risk management aimed at risk reduction."),
    ),
    "ndma-flood-guidelines-2008-p21-c3": (
        ("The objectives include strengthening emergency response capabilities and improving the compliance regime.", "Restates objectives 8 and 9."),
        ("The guidelines aim to flood-proof every structure in flood-prone areas, including private homes.", "SCOPE_OVERSTATEMENT", "The objective covers strategic and public utility structures only."),
        ("Capacity development is excluded from the objectives of the guidelines.", "CONTRADICTION", "Objective 7 introduces capacity development interventions."),
    ),
    "ndma-national-disaster-management-plan-2019-p113-c1": (
        ("According to Census 2011, India had nearly 104 million elderly persons, and 71% of them lived in rural areas.", "Restates two census figures."),
        ("Census 2011 counted nearly 104 million elderly persons, including about 20 million with disabilities.", "POPULATION_MISMATCH", "The elderly total is stated; a disabled sub-population figure is not."),
        ("The life expectancy at birth in India is 75 years for both men and women.", "SAME_TOPIC_WRONG_CLAIM", "The passage gives 69.3 years for females and 65.8 years for males."),
    ),
    "ndma-flood-guidelines-2008-p68-c2": (
        ("Real-time transmission of data from hydrological and hydrometeorological stations to forecasting centres is a vital part of the flood forecasting system.", "Paraphrases the data-transmission point."),
        ("The IMD's flood meteorological offices supply daily rainfall data and heavy-rainfall warnings to the CWC's forecasting centres, under the direction of the NDMA.", "ACTOR_MISMATCH", "The IMD-to-CWC data flow is stated; NDMA direction is added."),
        ("Landline telephone and telegram links are still the main way of transmitting flood forecasting data.", "CONTRADICTION", "Landlines were common only until the early 1970s; communication is now mainly wireless."),
    ),
    "ndma-flood-guidelines-2008-p40-c0": (
        ("The Government of India's past flood initiatives include the Policy Statement of 1954 and the High Level Committee on Floods of 1957.", "Restates two listed initiatives."),
        ("The Ministers' Committee on Flood Control was set up in 1964 and submitted its report within six months.", "TIMING_ADDITION", "The 1964 committee is listed; the six-month report is invented."),
        ("The Government of India issued no policy statements on floods before 1980.", "CONTRADICTION", "Policy statements of 1954, 1956 and 1958 are listed."),
    ),
    "ndma-national-disaster-management-plan-2019-p65-c2": (
        ("Over the last ten years, about 2,500 people a year in India died from lightning strikes and torrential rain.", "Restates the casualty figure."),
        ("Experts expect thunderstorms and dust storms to become more severe in every Indian state.", "SCOPE_OVERSTATEMENT", "Rising severity is expected for India; 'every state' is not stated."),
        ("Experts expect thunderstorms and dust storms to become less frequent as global temperatures rise.", "CONTRADICTION", "They expect severity and frequency to rise."),
    ),
    "ndma-flood-guidelines-2008-p148-c0": (
        ("Under the model bill, the state government may bring different provisions into force on different dates for different areas or rivers.", "Paraphrases the commencement proviso."),
        ("Under the model bill, the state government must apply different commencement dates to different rivers.", "MODALITY_OVERSTATEMENT", "Different dates 'may be appointed'; the claim makes it compulsory."),
        ("The model bill's definition of flood plain excludes the water channel and the flood channel.", "CONTRADICTION", "The definition includes the water channel and the flood channel."),
    ),
    "ndma-national-disaster-management-plan-2019-p341-c2": (
        ("Community training programmes should be socially inclusive, with special emphasis on women, children, the elderly, SC/ST and persons with disabilities.", "Restates the inclusion guidance."),
        ("Responsibility for community leadership and motivation will rest with local authorities, PRIs and ULBs, with the NDRF in overall charge.", "ACTOR_MISMATCH", "Local authorities, PRIs and ULBs under State and District guidance are named; NDRF charge is invented."),
        ("The India Disaster Resource Network is a printed directory that covers only a few types of equipment.", "CONTRADICTION", "IDRN is a web-based, nation-wide inventory covering almost all basic needs."),
    ),
    "ndma-flood-guidelines-2008-p154-c0": (
        ("When determining compensation, restrictions on the land under any other law in force are to be taken into consideration.", "Paraphrases sub-section (2)."),
        ("Compensation may not exceed the difference in land value caused by the restriction, and is capped at 50 percent of the land's market value.", "NUMERIC_ADDITION", "The difference-in-value ceiling is stated; the 50 percent cap is invented."),
        ("Restrictions imposed on the land under other laws must be ignored when compensation is determined.", "CONTRADICTION", "They are to be taken into consideration."),
    ),
}


def _words(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def walk(prepared) -> tuple[list[dict], list[tuple[str, str, dict]]]:
    v3 = json.loads(V3_CHALLENGE.read_text(encoding="utf-8"))
    v3_pages = {(row["source_id"], row["page"]) for row in v3}
    candidates = sorted(
        (hashlib.sha256(("14d-v1:" + chunk_id).encode("utf-8")).hexdigest(), chunk_id, text, meta)
        for chunk_id, text, meta in zip(prepared.ids, prepared.documents, prepared.metadatas)
        if (meta["source_id"], int(meta["page"])) not in v3_pages and len(text) >= 400
    )
    log, accepted = [], []
    for _, chunk_id, text, meta in candidates:
        reason = SKIPS.get(chunk_id)
        if reason is None:
            words = _words(text)
            if any(len(words & _words(other)) / len(words) >= 0.8 for _, other, _ in accepted):
                reason = "NEAR_DUPLICATE"
        if reason is not None:
            log.append({"chunk_id": chunk_id, "decision": "SKIPPED", "reason": reason})
            continue
        accepted.append((chunk_id, text, meta))
        log.append({"chunk_id": chunk_id, "decision": "ACCEPTED_TEST" if len(accepted) <= 45 else "ACCEPTED_PRACTICE",
                    "reason": None})
        if len(accepted) == 55:
            break
    return log, accepted


def fingerprint(rows: list[dict]) -> str:
    lines = [json.dumps([row[field] for field in FIELDS], ensure_ascii=False, separators=(",", ":"))
             for row in sorted(rows, key=lambda row: row["claim_pair_id"])]
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def build() -> dict[str, object]:
    with contextlib.redirect_stdout(io.StringIO()):
        prepared = prepare_corpus()
    log, accepted = walk(prepared)
    if [chunk_id for chunk_id, _, _ in accepted] != list(CLAIMS):
        raise ValueError("accepted chunks do not match CLAIMS (order or membership)")
    if set(SKIPS) - {entry["chunk_id"] for entry in log}:
        raise ValueError("a judgement skip was never walked")
    sets: dict[str, list[dict]] = {"test": [], "practice": []}
    for number, (chunk_id, text, meta) in enumerate(accepted, 1):
        name, prefix, index = ("test", "T", number) if number <= 45 else ("practice", "P", number - 45)
        (s_claim, s_reason), (p_claim, p_sub, p_reason), (u_claim, u_sub, u_reason) = CLAIMS[chunk_id]
        for k, (label, claim, subtype, reason) in enumerate((
            ("SUPPORTED", s_claim, "SUPPORTED_PARAPHRASE", s_reason),
            ("PARTIALLY_SUPPORTED", p_claim, p_sub, p_reason),
            ("UNSUPPORTED", u_claim, u_sub, u_reason),
        ), 1):
            sets[name].append({
                "claim_pair_id": f"{prefix}{index:02d}-C{k}", "challenge_set": name, "chunk_id": chunk_id,
                "source_id": str(meta["source_id"]), "filename": str(meta["source_document"]),
                "page": int(meta["page"]), "passage_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "claim": claim, "construction_label": label, "construction_reason": reason, "reason_subtype": subtype,
                "synthetic_variant": True, "not_authoritative_policy": True, "benchmark_version": CHALLENGE_ID,
                "construction_protocol_version": CONSTRUCTION_PROTOCOL,
            })
    claims = [row["claim"] for rows in sets.values() for row in rows]
    if len(claims) != len(set(claims)):
        raise ValueError("claims must be unique")
    manifest_sets = {}
    for name, rows in sets.items():
        for label, expected in MIX[name].items():
            got = Counter(row["reason_subtype"] for row in rows if row["construction_label"] == label)
            if got != expected:
                raise ValueError(f"{name} {label} subtype mix {dict(got)} != {expected}")
        manifest_sets[name] = {
            "claim_pairs": len(rows),
            "label_counts": dict(sorted(Counter(row["construction_label"] for row in rows).items())),
            "reason_subtype_counts": dict(sorted(Counter(row["reason_subtype"] for row in rows).items())),
            "chunk_ids": list(dict.fromkeys(row["chunk_id"] for row in rows)),
            "challenge_fingerprint": fingerprint(rows),
        }
    v3 = json.loads(V3_CHALLENGE.read_text(encoding="utf-8"))
    manifest = {
        "challenge_id": CHALLENGE_ID, "construction_protocol_version": CONSTRUCTION_PROTOCOL,
        "corpus_version": CORPUS_VERSION, "corpus_fingerprint": CORPUS_FINGERPRINT,
        "selection_rule": SELECTION_RULE, "canonical_fields_in_order": list(FIELDS), "sets": manifest_sets,
        "excluded_v3_pages": [list(page) for page in sorted({(row["source_id"], row["page"]) for row in v3})],
        "provenance": ("Construction-labeled by Lead under the V3 construction rules; not human gold. Claims are "
                       "synthetic benchmark material, not NDMA guidance. No model output was used."),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in sets.items():
        (OUT / f"challenge_{name}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n",
                                                   encoding="utf-8", newline="\n")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8", newline="\n")
    (OUT / "selection_log.json").write_text(json.dumps({"walked": log}, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8", newline="\n")
    return manifest


def main() -> int:
    manifest = build()
    for name, info in manifest["sets"].items():
        print(f"{name}: {info['claim_pairs']} pairs, fingerprint {info['challenge_fingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
