"""Assessment Agent — quiz generation, scoring, EMA updates, re-plan triggers.

Quiz composition (per PRD):
  - 60% Multiple Choice
  - 30% Short Answer
  - 10% Applied / Code Scenario

LLM-as-judge for short-answer grading.
Emits re-plan signal after scoring.
"""
import json
import uuid
from app.core.llm_client import chat_complete

QUIZ_GEN_SYSTEM = """You are Wozly's Assessment Agent. Generate a quiz for a learner.

RULES:
1. Generate between 5 and 10 questions total.
2. Exactly 60% must be multiple_choice, 30% short_answer, 10% applied.
3. Difficulty must match the knowledge_level provided.
4. Questions must be generated FRESH — never reuse generic examples.
5. Each question must be clearly tied to one of the provided topics.
6. For multiple_choice: provide exactly 4 options labeled A-D with one correct answer.
7. For short_answer: provide a model answer and a grading rubric.
8. For applied: provide a realistic scenario requiring the learner to apply knowledge.
9. Return ONLY valid JSON — no markdown, no explanation.

OUTPUT FORMAT:
{
  "questions": [
    {
      "id": "q1",
      "type": "multiple_choice",
      "topic": "<topic name>",
      "question": "<question text>",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "correct_answer": "A",
      "rubric": null
    },
    {
      "id": "q2",
      "type": "short_answer",
      "topic": "<topic name>",
      "question": "<question text>",
      "options": null,
      "correct_answer": "<model answer>",
      "rubric": "<grading rubric for LLM judge>"
    },
    {
      "id": "q3",
      "type": "applied",
      "topic": "<topic name>",
      "question": "<scenario description>",
      "options": null,
      "correct_answer": "<expected approach/answer>",
      "rubric": "<rubric for evaluation>"
    }
  ]
}"""

SHORT_ANSWER_JUDGE_PROMPT = """You are grading a learner's short-answer response for a quiz.

Question: {question}
Model Answer: {correct_answer}
Grading Rubric: {rubric}
Learner's Answer: {learner_answer}

Score the learner's answer from 0.0 to 1.0 based on the rubric.
Consider partial credit — a partially correct answer should score 0.3–0.7.
Return ONLY a JSON object: {{"score": 0.8, "feedback": "brief explanation"}}"""


async def generate_quiz(
    topics: list[str],
    knowledge_level: str,
    domain: str,
    week_number: int,
) -> list[dict]:
    # Handle both string topics and rich topic objects
    topic_names = [t.get("name") if isinstance(t, dict) else str(t) for t in topics]
    topic_list = ", ".join(topic_names)
    user_message = (
        f"Domain: {domain}\n"
        f"Knowledge Level: {knowledge_level}\n"
        f"Week: {week_number}\n"
        f"Topics covered this week: {topic_list}\n\n"
        f"Generate the quiz now."
    )

    try:
        raw = await chat_complete(
            system=QUIZ_GEN_SYSTEM,
            user=user_message,
            role="assessment",
            temperature=0.7,
            max_tokens=3000,
            json_mode=True,
        )
        try:
            data = json.loads(raw)
            questions = data.get("questions", [])
        except json.JSONDecodeError:
            questions = []
    except Exception as e:
        print(f"[Assessment] LLM quiz generation failed ({e}), using fallback questions.")
        questions = []

    # Fallback: generate hardcoded questions if LLM failed
    if not questions:
        questions = _fallback_questions(topics, knowledge_level)

    # Assign fresh UUIDs
    for q in questions:
        q["id"] = str(uuid.uuid4())

    return questions


def _fallback_questions(topics: list[str], level: str) -> list[dict]:
    """Hardcoded fallback questions that never fail."""
    questions = []
    for i, topic in enumerate(topics[:3]):
        questions.append({
            "id": f"q{i*3+1}",
            "type": "multiple_choice",
            "topic": topic,
            "question": f"Which of the following best describes the primary purpose of {topic}?",
            "options": [
                f"A. To provide a foundational framework for understanding {topic}",
                f"B. To replace all existing approaches in the field",
                f"C. To serve only as a theoretical concept with no practical application",
                f"D. To eliminate the need for further learning",
            ],
            "correct_answer": "A",
            "rubric": None,
        })
        questions.append({
            "id": f"q{i*3+2}",
            "type": "multiple_choice",
            "topic": topic,
            "question": f"What is a key advantage of applying {topic} in real-world scenarios?",
            "options": [
                f"A. It makes all problems trivially easy to solve",
                f"B. It provides structured approaches to complex problems",
                f"C. It completely automates the decision-making process",
                f"D. It requires no prior knowledge to implement",
            ],
            "correct_answer": "B",
            "rubric": None,
        })
    # Add a short answer
    if topics:
        questions.append({
            "id": f"q{len(questions)+1}",
            "type": "short_answer",
            "topic": topics[0],
            "question": f"In your own words, explain the core concept of {topics[0]} and why it is important in {topics[0].split()[0] if topics[0] else 'this'} domain.",
            "options": None,
            "correct_answer": f"{topics[0]} is important because it provides foundational knowledge that enables practitioners to build more complex solutions.",
            "rubric": "Award full marks for mentioning core principles. Partial credit for related concepts.",
        })
    return questions


async def grade_short_answer(
    question: str,
    correct_answer: str,
    rubric: str,
    learner_answer: str,
) -> tuple[float, str]:
    """LLM-as-judge grading for short answer questions. Returns (score, feedback)."""
    prompt = SHORT_ANSWER_JUDGE_PROMPT.format(
        question=question,
        correct_answer=correct_answer,
        rubric=rubric or "Award full marks for conceptually correct answers.",
        learner_answer=learner_answer,
    )
    try:
        import asyncio
        raw = await asyncio.wait_for(
            chat_complete(
                system="",
                user=prompt,
                role="assessment",
                temperature=0,
                max_tokens=800,
                json_mode=True,
            ),
            timeout=8.0  # 8 seconds max wait
        )
        data = json.loads(raw)
        return float(data.get("score", 0.5)), data.get("feedback", "")
    except Exception as e:
        print(f"[Assessment] LLM grading failed or timed out ({e}), using fallback score.")
        return 0.5, "Could not grade automatically due to API error"


async def score_quiz(
    questions: list[dict],
    answers: list[dict],
) -> dict[str, float]:
    """
    Grade all submitted answers. Returns dict mapping question_id → score (0.0–1.0).
    """
    # Build answer lookup
    answer_map = {a["question_id"]: a["answer"] for a in answers}
    scores: dict[str, float] = {}

    for q in questions:
        qid = q["id"]
        learner_answer = answer_map.get(qid, "")
        q_type = q.get("type", "multiple_choice")

        if q_type == "multiple_choice":
            correct = (q.get("correct_answer") or "").strip().upper()
            given = learner_answer.strip().upper()
            # Accept "A", "A.", or the full option text starting with A
            scores[qid] = 1.0 if (given == correct or given.startswith(correct)) else 0.0

        elif q_type in ("short_answer", "applied"):
            score, _ = await grade_short_answer(
                question=q.get("question", ""),
                correct_answer=q.get("correct_answer", ""),
                rubric=q.get("rubric", ""),
                learner_answer=learner_answer,
            )
            scores[qid] = score

    return scores


def aggregate_topic_scores(
    questions: list[dict],
    scores: dict[str, float],
) -> dict[str, float]:
    """
    Average scores per topic from raw per-question scores.
    Returns dict mapping topic_name → average_score (0.0–1.0).
    """
    topic_scores: dict[str, list[float]] = {}
    for q in questions:
        topic = q.get("topic", "general")
        qid = q["id"]
        if qid in scores:
            topic_scores.setdefault(topic, []).append(scores[qid])

    return {
        topic: round(sum(vals) / len(vals), 4)
        for topic, vals in topic_scores.items()
    }


def determine_next_action(topic_averages: dict[str, float]) -> str:
    """
    Determine overall next action based on topic score distribution.
    Returns 'continue', 'review', or 'replan'.
    """
    if not topic_averages:
        return "continue"
    
    avg_all = sum(topic_averages.values()) / len(topic_averages)
    
    # User must score at least 60% overall to pass
    if avg_all >= 0.6:
        return "continue"
    else:
        return "replan"
