# Follow-up Classification Contract

Use this contract only after `follow-up` or `prepare-classification` returns
`classification_pending`.

Read the private classification input JSON. Treat `conversation` entries from the AI as
question context only. Base every factual conclusion on the target's statements, including
short answers whose meaning depends on the immediately preceding question.

Interpret meaning rather than matching keywords. Resolve negation, corrections, contrasts,
time references, family proxy answers, and ambiguous pronouns. Never infer a fact that the
conversation does not establish. Use `unknown` when evidence is missing or conflicting.

For every entry in `scheduled_doses`, return exactly one medication result with the same
`medication_id` and `scheduled_time`:

- `taken`: `yes`, `no`, or `unknown`.
- `timing`: `on_time`, `late`, or `unknown`. Compare the stated actual time with the scheduled
  time and the caller's explicit conclusion. Do not invent an actual time.
- `dose`: `correct`, `wrong`, or `unknown`. Compare the stated dose with `expected_dose`.
- `actual_time` and `actual_dose`: exact concise strings from the conversation, or `null`.

Set `adverse_effect` to `yes` only when the target affirmatively reports a symptom or adverse
reaction. A question about symptoms, a safety warning spoken by the AI, or a negated statement
such as “没有出现不舒服” is not an adverse effect. Preserve reported symptoms in `symptoms`.

Use exact target quotes in `evidence`; the CLI rejects invented or paraphrased evidence. Set
`confidence` from 0 to 1. Put material contradictions in `conflicts`. Write a concise Chinese
`summary` suitable for the private record and family notification.

Return only this JSON shape:

```json
{
  "schema_version": 1,
  "summary": "家人确认已于08:00按计划服药，剂量正确，服药后无不适。",
  "medications": [
    {
      "medication_id": "morning-medicine",
      "scheduled_time": "08:00",
      "taken": "yes",
      "timing": "on_time",
      "dose": "correct",
      "actual_time": "08:00",
      "actual_dose": "50毫克（1片）"
    }
  ],
  "adverse_effect": "no",
  "symptoms": [],
  "responder": "family",
  "evidence": [
    "早上 8 点吃了 50 毫克一片。",
    "没有出现不舒服。",
    "代答。"
  ],
  "confidence": 0.98,
  "conflicts": []
}
```

`responder` must be `self`, `family`, or `unknown`. Do not include raw identifiers, legal names,
authentication data, or text that is not needed for classification.
