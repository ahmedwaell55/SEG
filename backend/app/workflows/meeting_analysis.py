from app.agents.nodes import full_analysis_agent, transcript_cleaner_agent
from app.agents.state import AnalysisState


async def analyze_transcript(transcript: str) -> dict:
    state: AnalysisState = {"raw_transcript": transcript}

    # Call 1: Clean the transcript
    state = {**state, **(await transcript_cleaner_agent(state))}

    # Call 2: Full analysis in a single LLM call
    state = {**state, **(await full_analysis_agent(state))}

    return {
        "cleaned_transcript": state.get("cleaned_transcript", transcript),
        "speaker_report": state.get("speaker_report", {}),
        "report": state["final_report"],
    }
