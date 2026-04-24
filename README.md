# ClaimSense AI

**AI-Powered Claim Denial Analysis for Healthcare RCM**

ClaimSense ingests EDI 835 (remittance) and EDI 837 (claim submission) data and automatically performs root cause analysis, historical pattern matching, and batch clustering on denied insurance claims.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ClaimSense Pipeline                         │
│                                                                     │
│   EDI 835 + EDI 837  ──►  DataLoader (join on ClaimID)             │
│                                   │                                 │
│                    ┌──────────────┼──────────────┐                 │
│                    ▼              ▼              ▼                  │
│            DenialAnalyzer  PatternMatcher  BatchClusterer           │
│            (Problem 1)     (Problem 2)    (Problem 3)               │
│                    │              │              │                  │
│                    │     OpenAI GPT-4o           │                  │
│                    │     text-embedding-3-small   │                  │
│                    └──────────────┼──────────────┘                 │
│                                   ▼                                 │
│                         Structured JSON Output                      │
│                   (DenialAnalysis + PatternMatchResult              │
│                    + BatchIntelligenceReport)                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Module Breakdown

| Module | Problem | Description |
|--------|---------|-------------|
| `src/models.py` | — | Pydantic models for EDI 835/837 + all output types |
| `src/data_loader.py` | — | Loads, joins, and serializes claim data |
| `src/llm_client.py` | — | OpenAI wrapper with retry, JSON mode, cost tracking |
| `src/denial_analyzer.py` | 1 | Root cause analysis per denied claim |
| `src/pattern_matcher.py` | 2 | Embedding + structured field similarity matching |
| `src/batch_clusterer.py` | 3 | Rule-based + K-means clustering + LLM enrichment |
| `src/pipeline.py` | All | Orchestrates all three modules end-to-end |
| `main.py` | CLI | Rich terminal interface for all commands |
| `prompts/` | All | Prompts stored separately for easy evaluation |

---

## Setup

### Prerequisites
- Python 3.10+
- An OpenAI API key

### Install
```bash
git clone <your-repo-url>
cd ClaimSense

pip install -r requirements.txt

cp .env.example .env
# Edit .env and set your OPENAI_API_KEY
```

### Environment Variables
```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o           # or gpt-4o-mini for lower cost
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

---

## Usage

### Run the demo (4 sample claims from the assignment brief)
```bash
python main.py demo
```

### Analyze all denied claims (Problems 1 + 2)
```bash
python main.py analyze --output results/analysis.json
```

### Analyze a single claim
```bash
python main.py analyze --claim CLM-2026-00142
```

### Batch clustering report (Problem 3)
```bash
python main.py batch --output results/batch.json
```

### Full pipeline (all three problems)
```bash
python main.py full
```

### Run tests
```bash
python -m pytest tests/ -v
```

---

## Problems Solved

### Problem 1: Claim Denial Root Cause Analysis

**What it does:**
- Joins 835 + 837 data for each denied claim
- Goes beyond the raw CARC code to understand *why* this specific claim was denied using actual field values
- Computes `days_from_service_to_received` for timely filing analysis
- Checks `ec_PriorAuthorization`, `ec_DelayReasonCode`, `pcl_RemarkCodes` for specific denial signals
- Returns: root cause, CARC interpretation, recoverability verdict (`recoverable / not_recoverable / needs_review`), confidence score, supporting evidence, recommended action

**Example output:**
```json
{
  "claim_id": "CLM-2026-00142",
  "denial_root_cause": "This Commercial claim (BCBS) was submitted 278 days after the service date of 2025-06-15, exceeding the typical 180-day Commercial filing limit. No delay reason code was provided to justify the late submission.",
  "carc_interpretation": "CARC 29 (Timely Filing) means the payer received the claim after their contractual filing deadline. The CO group means this is a provider write-off.",
  "recoverability": "not_recoverable",
  "confidence_score": 0.93,
  "supporting_evidence": [
    "ec_ServiceDateFrom: 2025-06-15",
    "pc_ReceivedDate: 2026-03-20",
    "derived.days_from_service_to_received: 278",
    "ec_DelayReasonCode: (empty — no justification provided)",
    "pc_InsuranceType: Commercial (typical window: 90-180 days)"
  ],
  "recommended_action": "Write off the $4,500.00 balance as the filing window has definitively passed with no delay justification."
}
```

### Problem 2: Historical Pattern Matching

**What it does:**
- Indexes all historical claims using OpenAI `text-embedding-3-small` embeddings
- Retrieves top-k most similar claims using a **weighted combined score**:
  - 55% embedding cosine similarity (semantic)
  - 45% structured field matching (payer=35%, procedure=30%, insurance type=15%, CARC=10%, diagnosis chapter=10%)
- Uses an LLM to analyze the pattern and recommend an appeal strategy
- Identifies systemic patterns (e.g., "Aetna denies CPT 72148 without prior auth at 65% rate")

**Why this weighting?** Payer and procedure code are the strongest predictors of payment behavior — a claim from the same payer for the same procedure that was paid last month is very strong evidence. Semantic embeddings catch edge cases where claims are worded differently but clinically equivalent.

**Example output:**
```json
{
  "denied_claim_id": "CLM-2026-00391",
  "systemic_pattern": "Aetna denies CPT 72148 (lumbar MRI) without prior authorization at a high rate",
  "historical_appeal_success_rate": 0.80,
  "pattern_analysis": "We found 1 historically paid claim (CLM-2025-08774) from Aetna for the same procedure (CPT 72148) with the same diagnosis (M54.5). The key differentiator: the paid claim had prior authorization AUTH-776655, while the denied claim has no auth. This suggests the denial is fixable — obtain retroactive auth or appeal with medical necessity documentation."
}
```

### Problem 3: Denial Clustering & Batch Intelligence

**What it does:**
- **Primary clustering**: groups by `payer + CARC code` (most interpretable and actionable)
- **Semantic sub-clustering**: for large homogeneous groups, applies K-means on embeddings to find procedure-level sub-patterns
- **LLM enrichment**: generates human-readable labels, billing-team-ready summaries, and recommended actions for each cluster
- **Top opportunity selection**: scores clusters on `denied_amount × estimated_recoverability` to surface the single highest-value recoverable cluster

**Example output:**
```
⭐ Cluster: Cigna | CARC-197 — Prior Authorization Missing
Claims: 2 | Denied: $19,800.00 | Payer: Cigna | CARC: 197

You have 2 claims from Cigna denied for missing prior authorization (CPT 43239 — EGD 
with biopsy, CPT 70553 — Brain MRI), totaling $19,800. Based on historical data, 80% 
of similar authorized claims were paid by Cigna. 

Action: Contact Cigna's provider line to request retroactive authorization for both 
claims. Attach physician orders, clinical notes, and urgency documentation. Submit 
within 30 days of this denial date.
```

---

## Design Decisions

### Why GPT-4o?
GPT-4o offers the best balance of reasoning quality and cost for healthcare RCM analysis. The domain requires understanding nuanced relationships between diagnosis codes, procedure codes, payer policies, and filing deadlines — a task that benefits from a frontier model. For production at scale, `gpt-4o-mini` can be used for simple CARC lookups, reserving GPT-4o for complex multi-factor analysis.

### Why text-embedding-3-small for similarity?
- 1536-dimension embeddings capture semantic relationships between medical claims
- Much cheaper than text-embedding-3-large with minimal quality loss for structured data
- Allows cosine similarity across the full claim context (payer + procedure + diagnosis + denial reason)

### Why rule-based clustering first, then semantic sub-clustering?
Billing teams need **interpretable** clusters. "Aetna CARC-29 claims" is actionable. "Cluster #4" is not. Rule-based clustering on payer+CARC gives directly actionable groups. Semantic sub-clustering is applied only to large groups (≥5 claims) to further differentiate by procedure/diagnosis patterns.

### Prompts stored separately
All three LLM prompts are in `prompts/` as plain text files. This allows:
- Easy evaluation and iteration without touching code
- Clear separation of "what to do" (code) vs "how to reason" (prompts)
- Version control on prompt changes independently

### Structured JSON output with Pydantic
All LLM outputs are validated through Pydantic models. Invalid recoverability values default to `needs_review`. Confidence scores are clamped to `[0, 1]`. This prevents hallucinations from propagating silently into downstream systems.

### Trade-offs considered
| Option | Chosen | Alternative | Reason |
|--------|--------|-------------|--------|
| Embedding model | text-embedding-3-small | ada-002 / large | Better quality, lower cost than ada; sufficient for structured claim data |
| Clustering | Rule-based + K-means | Pure semantic | Rule-based is interpretable; semantic fills gaps |
| LLM temp | 0.1 | 0.0 | Slight variation avoids degenerate outputs on edge cases |
| Vector DB | In-memory list | ChromaDB/Pinecone | Sufficient for ≤10K claims; production would use a proper vector store |

---

## Known Limitations

1. **In-memory vector store**: The current PatternMatcher stores embeddings in RAM. For production scale (millions of claims), this should be replaced with a proper vector database (ChromaDB, Pinecone, pgvector).

2. **Single-level line data**: The current schema assumes one service line per claim. Real 835/837 data often has multiple lines per claim. The data model supports extension but the analysis logic assumes a primary line.

3. **No payer-specific filing window database**: Timely filing analysis uses general rules (Medicare=365, Commercial≈180 days). A production system would maintain a per-payer-per-plan filing window database.

4. **Synthetic dataset**: The 22-claim dataset covers key denial scenarios but is insufficient for training pattern matchers in production. Real-world performance would require thousands of historical claims.

5. **LLM hallucination guard**: We validate structure (Pydantic) and clamp numeric ranges, but we don't cross-verify LLM citations against actual claim field values. A production system would add a verification step.

### What I Would Do With More Time
- Add a proper vector database (ChromaDB) with persistence across sessions
- Build a payer-specific policy database (filing windows, covered services, auth requirements)
- Add an evaluation framework: run the analyzer on labeled claims, measure precision/recall of recoverability predictions
- Add streaming output for the CLI (long LLM calls feel slow without progress feedback)
- Add async batch processing (currently sequential LLM calls)
- Integrate with real EDI parsing (using `pyx12` or `python-edi` libraries)

---

## Evaluation Approach

### How I know the system is working

1. **Unit tests** (30 tests, all passing): Cover data loading, model validation, edge cases (invalid CARC codes, non-denied claims, out-of-range confidence scores)

2. **Scenario validation**: The synthetic dataset includes known-truth scenarios (e.g., CLM-2026-00142 is definitively a late-filing denial at 278 days). I verified the system correctly identifies these.

3. **Recoverability accuracy**: I manually labeled the 11 denied claims in the dataset and compared against system output:
   - CARC 29 with no delay code → system correctly identifies as `not_recoverable`
   - CARC 197 with empty auth → system correctly identifies as `needs_review` / `recoverable`
   - CARC 18 (duplicate) → system correctly identifies as `not_recoverable`

4. **Pattern matching sanity**: The system correctly ranks same-payer + same-procedure claims higher than cross-payer matches, validating the weighted scoring approach.

---

## Dataset

The `data/synthetic_claims.json` file contains **22 claims** (11 denied, 11 paid) covering:

| Denial Type | CARC | Claims |
|-------------|------|--------|
| Timely Filing | 29 | 3 |
| Missing Information | 16 | 1 |
| Medical Necessity | 50 | 2 |
| Duplicate | 18 | 1 |
| Prior Auth Missing | 197 | 2 |
| Coding/Modifier Error | 4 | 1 |
| Non-Covered Service | 96 | 1 |
| Documentation Required | 252 | 1 |
| **Paid (various)** | — | 11 |

Payers represented: Blue Cross Blue Shield, Medicare Part B, Aetna, United Healthcare, Cigna  
Procedures represented: 99213, 99214, 99215 (E&M), 27447 (knee replacement), 72148 (MRI spine), 70553 (MRI brain), 43239 (EGD), 29827 (shoulder surgery), 90837 (therapy)

---

## Cost Estimate

Running the full pipeline on 11 denied claims:
- **GPT-4o**: ~$0.15–0.25 per full run (analysis + pattern + batch)
- **Embeddings**: ~$0.001 per run (22 claims × ~200 tokens each)
- **Total**: ~$0.15–0.25 per demo run

For production scale (1,000 denied claims/day):
- Use `gpt-4o-mini` for simple cases: ~$3–5/day
- Reserve `gpt-4o` for complex multi-factor denials: ~$20–30/day
- Embeddings: ~$0.10/day
