# Viva practice bank — private draft

These answers describe the simulated prototype at RESTRICTED disclosure. They are prompts for the student to check against their own work and understanding, not statements of the student's personal contribution.

### Q1. What practical problem does Sentinel-Agent address? [topic: problem]

**Answer:** It brings route, shelter, population and evidence views together for a simulated flood-evacuation decision. The operator can inspect a suggestion and its audit trail before acting. The research question concerns transparent decision support, not a claim of real-world effectiveness.

### Q2. Why use Fort Kochi roads? [topic: road-graph]

**Answer:** Real topology makes route connectivity and the visual layout concrete. The incidents and hazards remain simulated, so a geographically realistic map must not be treated as a live road-status source.

### Q3. Which incident values are real and which are simulated? [topic: data]

**Answer:** The road topology is based on Fort Kochi data. Flood severity, group demand, shelter states, closures and operator choices in the tests are simulated. The console repeats that distinction on operational pages.

### Q4. What does the road graph contribute to the method? [topic: road-graph]

**Answer:** It supplies connected nodes and edges for candidate routes between zones and shelters. It cannot tell the system whether a road is currently open in a real emergency without an authoritative live data source.

### Q5. What is a hazard future in this project? [topic: hazard-model]

**Answer:** It is one simulated continuation of uncertain hazard and route conditions. The model samples such continuations to study possible decisions under its assumptions. They are model outputs, not observed forecasts for an active incident.

### Q6. How should an operator read the honesty banner? [topic: ethics]

**Answer:** “REAL ROAD TOPOLOGY · SIMULATED DISASTER CONDITIONS · NOT OPERATIONALLY VALIDATED” means the map is geographically grounded but the incident and decisions are research simulations. It rules out field dispatch use.

### Q7. Which planners were compared in the frozen study? [topic: planners]

**Answer:** The held-out V3 report compares several non-learned planners and a learned policy family under a frozen protocol. The named principal comparator was risk-greedy, while stronger lookahead rows were reported separately. The details and limits are in the frozen policy evaluation. [3]

### Q8. What did the learned policy study conclude? [topic: reinforcement-learning]

**Answer:** The evaluated reinforcement-learning family did not meet its preregistered benefit gate against the named comparator on the frozen synthetic suite. The result is retained as a negative finding rather than hidden or retuned after seeing the test set. [3][5]

### Q9. How were training and evaluation separated? [topic: reproducibility]

**Answer:** The training procedure and checkpoint-selection rule were frozen before the held-out policy comparison. The held-out scenarios were not used to choose a new checkpoint. This protects the meaning of the reported negative result. [3][5]

### Q10. What does a retrieval direct hit measure? [topic: retrieval]

**Answer:** It measures whether a judged relevant passage appears within the reported cutoff in the frozen benchmark. It does not prove that the passage supports the precise wording of a proposed operational rule.

### Q11. What was the retrieval verdict and its labeling limit? [topic: retrieval]

**Answer:** The hybrid method met its preregistered comparison against dense retrieval. The benchmark relevance labels were AI assisted and are not independent human gold; the source report also documents a pre-metric coverage extension. [4]

### Q12. Why is claim-support verification separate from retrieval? [topic: claim-support]

**Answer:** Retrieval can find a related passage even when that passage does not support a numeric threshold or a stronger conclusion. Verification asks whether the exact claim follows from the cited source span.

### Q13. What happened in the claim-support sequence? [topic: claim-support]

**Answer:** 14C failed its macro-score and span-integrity conditions. 14D became the evaluation of record under a frozen replacement protocol and a user approval for its T2-use verdict. 14B was superseded and was never scored. [7]

### Q14. Does a useful verifier make every document rule T2? [topic: rule-tiers]

**Answer:** No. Each rule still has to be supported by its own source passage. NDMA-R01 and NDMA-R02 remain T1 after partially supported answers; the current result contains no T2 rule. [8]

### Q15. How are rule tiers shown in the console? [topic: rule-tiers]

**Answer:** The table reads the recorded tiering result and its provenance. If the result is missing or stale, it leaves the tier unavailable with a reason instead of inferring a value from the verifier score.

### Q16. What is the approved short description of the gate? [topic: gate]

**Answer:** Before a dispatch, Sentinel checks sampled hazard futures against a fixed statistical bar. It allows a dispatch only when the lower bound clears that bar; otherwise it holds and escalates. A certificate records each decision for replay. The restricted report contains the exact approved paragraph.

### Q17. What does HOLD mean? [topic: gate]

**Answer:** HOLD is a deliberate, visible decision when no dispatch option clears the required bar or another reason blocks commitment. It leaves the choice and its escalation in the audit record rather than silently choosing a route.

### Q18. What does certificate replay establish? [topic: reproducibility]

**Answer:** Replay checks whether the recorded computation matches its stored inputs and certificate. It cannot prove that the inputs describe the real world, nor that a simulated decision is suitable for deployment.

### Q19. What does the tamper control do? [topic: reproducibility]

**Answer:** It changes a copy of the forecast-hash field for a replay request. A mismatch then identifies that altered field. The stored certificate remains unchanged.

### Q20. What was preregistered in the main evaluation? [topic: evaluation]

**Answer:** Phase 27 froze systems, regimes, metrics, decision bars and thresholds before the final comparison. Its bars are reported as pass or fail without changing their meaning after the results appeared. [6]

### Q21. Which Phase 27 bars passed and failed? [topic: evaluation]

**Answer:** The safety bar passed, the outcome bar failed, the restricted decision-level comparison passed, and the variance bar failed. The outcome bar's guard R was 21.4 % below its 95 % requirement, so there is no outcome-effect claim. [6]

### Q22. Why not highlight only a favorable failure fraction? [topic: limitations]

**Answer:** That fraction must be read with the much lower movement throughput in the same preregistered comparison. R = 21.4 % below 95 % failed the outcome bar, so isolating the favorable fraction would misstate the result. [6]

### Q23. Is the guided demo an evaluation sample? [topic: limitations]

**Answer:** No. The seed was selected because the recorded run shows useful interface states, including hold, dispatch and a re-route. It teaches the workflow and does not estimate population-level performance.

### Q24. How does a live session differ from the recorded demo? [topic: gate]

**Answer:** The recorded demo replays a fixed operator choice. A live simulated session computes the current suggestion, shows alternatives and lets the operator record a new choice with a reason. It also displays re-checks for groups already on the road.

### Q25. What should happen if a result file is absent? [topic: data]

**Answer:** The evidence view shows a dash and a reason. It does not estimate a value or copy one from a design mock. The numbers ledger likewise names the exact artifact and field for each quoted result.

### Q26. What did the hardware work establish? [topic: hardware]

**Answer:** The hardware bridge and simulated publisher establish software paths for commands and acknowledgments. Without a completed physical bench run, a physical latency number remains unavailable and must not be reported.

### Q27. What safety issue remains before field use? [topic: ethics]

**Answer:** The prototype lacks real incident validation, current official hazard and road data, human-factors evidence under stress and an accountable operational approval process. It must remain research-only until those gaps are addressed.

### Q28. Why keep a failed predecessor evaluation visible? [topic: ethics]

**Answer:** Retaining 14C failed results and the 14B superseded status prevents selective reporting. It also makes clear that the later 14D evaluation of record answered a narrower, frozen question rather than erasing earlier limitations.

### Q29. What would be a useful next document study? [topic: future-work]

**Answer:** Find a source that actually states an evacuation-relevant threshold, register its provenance, and test the exact rule wording before assigning a tier. Improving the verifier cannot compensate for a source that lacks the needed statement.

### Q30. What is the next outcome experiment? [topic: future-work]

**Answer:** Any new configuration needs a newly preregistered study that measures both safety and movement throughput. The frozen Phase 27 result must remain unchanged; its failed outcome bar cannot be repaired by relabeling the same data. [6]
