"""
StadiumIQ Agent Module

Gemini-powered AI assistant that answers attendee questions
using live venue context from the tools module.
"""

import os
from typing import List, Optional

import google.generativeai as genai
from dotenv import load_dotenv

from tools import (
    get_crowd_density,
    get_queue_times,
    get_best_facility,
    get_exit_strategy,
    get_game_state,
    get_venue_name,
)

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# System prompt template
SYSTEM_PROMPT = """You are StadiumIQ, a smart venue assistant helping attendees \
at a large sporting event. You are helpful, concise, and \
proactive. You always prioritize attendee safety and comfort.

You have access to live venue data including crowd density, \
queue wait times, exit strategies, and game state. \
Use this data to give specific, actionable advice.

Current venue context:
- Venue: {venue_name}
- Attendee section: {section}
- Game state: {game_state}
- Crowd summary: Most crowded zone is {most_crowded}, \
least crowded is {least_crowded}
- Current time remaining: {time_remaining} minutes

Rules:
- Always be specific, never vague
- If asked about food or restrooms, always give wait times
- If asked about exits, always give the recommended gate
- If the match is in final 10 minutes, proactively mention exit planning
- Keep responses under 100 words unless the user asks for detail
- Never make up information not present in the venue context"""


class StadiumAgent:
    """Gemini-powered venue assistant that provides contextual advice to attendees.

    Uses live venue data from tools.py to build context-aware prompts
    and maintains a chat session with conversation history.
    """

    def __init__(self, user_section: str = "A1") -> None:
        """Initialize the StadiumAgent with a user's seat section.

        Args:
            user_section: The attendee's seat section (e.g., "A1", "B2").
                Defaults to "A1".
        """
        self.user_section: str = user_section
        self.history: List[dict] = []

        # Load initial context from tools
        self.crowd_data: dict = get_crowd_density()
        self.queue_data: list = get_queue_times()
        self.game_data: dict = get_game_state()
        self.exit_data: dict = get_exit_strategy(user_section)
        self.venue_name: str = get_venue_name()

        # Build system prompt with live data
        self.system_prompt: str = self._build_system_prompt()

        # Initialize Gemini model and chat session
        try:
            self.model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=self.system_prompt,
            )
            self.chat_session = self.model.start_chat(history=[])
        except Exception:
            self.model = None
            self.chat_session = None

    def _build_system_prompt(self) -> str:
        """Build the system prompt by filling in the template with live data.

        Returns:
            The formatted system prompt string with current venue context.
        """
        game_state_summary = (
            f"{self.game_data.get('event_name', 'Unknown')} — "
            f"{self.game_data.get('period', 'Unknown')} — "
            f"{self.game_data.get('status', 'unknown')}"
        )

        return SYSTEM_PROMPT.format(
            venue_name=self.venue_name,
            section=self.user_section,
            game_state=game_state_summary,
            most_crowded=self.crowd_data.get("most_crowded", "Unknown"),
            least_crowded=self.crowd_data.get("least_crowded", "Unknown"),
            time_remaining=self.game_data.get("time_remaining_minutes", "Unknown"),
        )

    def chat(self, user_message: str) -> str:
        """Send a message to the Gemini chat session with live venue context.

        Appends fresh crowd and queue data to the user message so Gemini
        always has up-to-date context for answering.

        Args:
            user_message: The attendee's question or message.

        Returns:
            The AI assistant's response text.
        """
        if not self.chat_session:
            return (
                "I'm having trouble connecting right now. "
                "Please check venue staff for assistance."
            )

        # Append live context to the message
        enriched_message = (
            f"User question: {user_message}\n\n"
            f"Live context refresh:\n"
            f"Venue: {get_venue_name()}\n"
            f"Queue times: {get_queue_times()}\n"
            f"Zone density: {get_crowd_density()}"
        )

        try:
            response = self.chat_session.send_message(enriched_message)
            response_text = response.text

            # Append to conversation history
            self.history.append({"role": "user", "content": user_message})
            self.history.append({"role": "assistant", "content": response_text})

            return response_text

        except Exception:
            return (
                "I'm having trouble connecting right now. "
                "Please check venue staff for assistance."
            )

    def refresh_context(self) -> None:
        """Re-call all tool functions and rebuild the system prompt with fresh data.

        Used when panels auto-refresh to ensure the agent has the latest
        venue information.
        """
        self.crowd_data = get_crowd_density()
        self.queue_data = get_queue_times()
        self.game_data = get_game_state()
        self.exit_data = get_exit_strategy(self.user_section)
        self.venue_name = get_venue_name()
        self.system_prompt = self._build_system_prompt()

    def get_proactive_alert(self) -> Optional[str]:
        """Check game state and return a proactive alert if applicable.

        Returns contextual alerts at key match moments:
        - At half-time: suggests best facilities to visit
        - In final 10 minutes: provides exit strategy

        Returns:
            A proactive alert message string, or None if no alert is needed.
        """
        game = get_game_state()

        if game.get("is_halftime"):
            # Find the facility with shortest queue
            food_queues = get_queue_times("food")
            restroom_queues = get_queue_times("restroom")

            best_food = food_queues[0] if food_queues else None
            best_restroom = restroom_queues[0] if restroom_queues else None

            parts = ["⏸️ Half-time! Great time to grab food or visit facilities."]
            if best_food and "error" not in best_food:
                parts.append(
                    f"Shortest food queue: {best_food['facility_id']} "
                    f"({best_food['wait_minutes']} min wait)."
                )
            if best_restroom and "error" not in best_restroom:
                parts.append(
                    f"Shortest restroom queue: {best_restroom['facility_id']} "
                    f"({best_restroom['wait_minutes']} min wait)."
                )

            return " ".join(parts)

        if game.get("is_final_10_minutes"):
            exit_info = get_exit_strategy(self.user_section)
            if "error" not in exit_info:
                return (
                    f"⚠️ Final 10 minutes! Your nearest exit is "
                    f"{exit_info['recommended_gate']} "
                    f"(estimated wait: {exit_info['estimated_wait']}). "
                    f"{exit_info['tip']}"
                )

        return None
