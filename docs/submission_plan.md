# Kaggle Submission Plan: ChessAdapt
**Deadline**: April 17, 2026

To maximize your chances of winning the $20,000 Metacognition or Executive Functions track, follow this structured plan to finalize your Kaggle submission.

## Phase 1: Data Preparation & Validation (April 14 - 15)

1. **Verify Task Files**: 
   - Ensure `data/tasks/t1_tasks.jsonl`, `t2_tasks.jsonl`, and `t3_tasks.jsonl` are fully populated (500 tasks total).
   - Valid FENs, valid rule descriptions, and the `prompt_template` should all be present.

2. **Run Final Evaluation on 3-5 Models**:
   - You need a "gradient" to show the benchmark works (e.g., GPT-4o > Llama-3-70b > Mistral-7b).
   - Use `make evaluate-all` or individual `make evaluate MODEL=...`.
   - **Metacognition Check**: Ensure the responses are being parsed correctly by `pipeline/prompt_builder_metacognition.py`.

3. **Generate Analysis Artifacts**:
   - Run `make analyze`.
   - Save the results as CSVs/JSONs in `data/results/`. These will be uploaded to Kaggle as part of your "Benchmark Results."

---

## Phase 2: Kaggle Platform Setup (April 15 - 16)

1. **Create the Kaggle Dataset**:
   - Go to [Kaggle Datasets](https://www.kaggle.com/datasets).
   - Upload your `data/tasks/` folder and `engine/` code.
   - Title: `ChessAdapt: Rule-Perturbed Chess dataset`.

2. **Create the Kaggle Benchmark**:
   - Navigate to the **Kaggle Benchmarks** tab (per the hackathon instructions).
   - "Attach" your dataset.
   - Link your `docs/writeup.md` content into the Benchmark description.

3. **Format the Writeup**:
   - Copy the content from your finalized `docs/writeup.md` into the Kaggle Benchmark description field.
   - **Pro Tip**: Use beautiful Markdown (tables, diagrams) to make it readable for the judges.

---

## Phase 3: Final Polish & Submission (April 16 - 17)

1. **Final Writeup Audit**:
   - Does it mention **Executive Functions**? (Yes: Inhibition, Flexibility).
   - Does it mention **Metacognition**? (Yes: Confidence Calibration).
   - Does it explain why chess is hard for AI? (Yes: Memorization prior).

2. **Code Zip**: 
   - Ensure the repository is clean.
   - Attach the codebase to your submission so judges can reproduce your `make test` results.

3. **SUBMIT**: 
   - Submit the URL of your Kaggle Benchmark before the deadline.

---

## Technical Tasks to Finish NOW

| Task | File | Status |
| :--- | :--- | :--- |
| Update README | `README.md` | ✅ Done |
| Integrate Metacognition in Writeup | `docs/writeup.md` | ✅ Done |
| Verify Metacognition Parsing | `pipeline/prompt_builder_metacognition.py` | ⚠️ Needs Test |
| Run Evaluation Gradient | `evaluation/runner.py` | ⚠️ Needs Execution |
