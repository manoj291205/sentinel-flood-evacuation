# References for the private draft

[1] National Disaster Management Authority, local source `ndma_temporary_shelters_2019.pdf`; cited passages and page identifiers are recorded in `data/constraints_v4/ndma_constraints.json`.

[2] OpenStreetMap contributors, Fort Kochi road network data. The repository's geospatial manifests and graph-generation records identify the extract and processing steps used here.

[3] Sentinel project, `V3_POLICY_EVALUATION.md`, frozen planner comparison and limitations.

[4] Sentinel project, `V3_RETRIEVAL_EVALUATION.md`, frozen retrieval comparison and limitations.

[5] Sentinel project, `V3_TRAINING_RESULT.md`, frozen reinforcement-learning result and limitations.

[6] Sentinel project, `specs/V4_EVALUATION_PREREG.md` and `specs/V4_D27_DECISION.md`, preregistered evaluation and its decision.

[7] Sentinel project, `data/eval_results/phase14d/test/score.json`, claim-support evaluation of record; `data/eval_results/phase14c/score.json`, the failed predecessor.

[8] Sentinel project, `data/constraints_v4/p15t2/tier_results.json`, approved-rule tiering result.

[9] Sentinel project, `data/eval_results/phase25/replay_batch.json` and `data/eval_results/phase26/`, certificate replay and in-transit re-check results.

## Methods and libraries used

[10] J. Schulman, F. Wolski, P. Dhariwal, A. Radford, O. Klimov, "Proximal Policy Optimization Algorithms," arXiv:1707.06347, 2017; trained through Stable-Baselines3 and sb3-contrib `MaskablePPO` (A. Raffin et al., "Stable-Baselines3: Reliable Reinforcement Learning Implementations," JMLR 22(268), 2021) on a Gymnasium environment.

[11] S. Robertson, H. Zaragoza, "The Probabilistic Relevance Framework: BM25 and Beyond," Foundations and Trends in Information Retrieval 3(4), 2009 (the BM25 retriever).

[12] G. V. Cormack, C. L. A. Clarke, S. Büttcher, reciprocal rank fusion, Proc. SIGIR 2009, pp. 758–759 (the hybrid retriever's rank fusion).

[13] N. Reimers, I. Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks," EMNLP 2019; the dense retriever uses the sentence-transformers library with the `all-MiniLM-L6-v2` model, run locally.

[14] A. Hagberg, D. Schult, P. Swart, "Exploring Network Structure, Dynamics, and Function using NetworkX," Proc. SciPy 2008 (road-graph routing).

[15] Software for the console and checks: FastAPI and Uvicorn (API), React with Vite and TypeScript (console), Playwright with axe-core (browser and accessibility tests), pytest and Hypothesis (Python tests), jsonschema (contract validation). Versions are pinned in `requirements*.txt` and `web/package-lock.json`.
