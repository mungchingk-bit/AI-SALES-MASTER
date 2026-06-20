from datetime import datetime

from core.role_engine import RoleEngine
from core.llm_client import get_client
from models.chat_message import ChatMessage
from models.style_profile import StyleProfile
from models.training_session import TrainingSession
from storage.session_store import SessionStore
from storage.style_store import StyleStore
from storage.weekly_review_store import WeeklyReviewStore

import config


class TrainingManager:
    def __init__(self):
        self.role_engine = RoleEngine()
        self.session_store = SessionStore()
        self.style_store = StyleStore()
        self.weekly_review_store = WeeklyReviewStore()
        self._active_sessions: dict[str, TrainingSession] = {}

    def create_session(
        self,
        mode: str,
        scenario: dict,
        style_profile_id: str | None = None,
    ) -> TrainingSession:
        """Create a new training session."""
        session = TrainingSession(
            mode=mode,
            scenario=scenario,
            style_profile_id=style_profile_id,
        )
        self._active_sessions[session.id] = session
        self.session_store.save(session)
        return session

    def get_session(self, session_id: str) -> TrainingSession | None:
        """Get a session by ID, checking active sessions first."""
        if session_id in self._active_sessions:
            return self._active_sessions[session_id]
        session = self.session_store.load(session_id)
        if session:
            self._active_sessions[session_id] = session
        return session

    def process_user_message(
        self, session_id: str, user_message: str
    ) -> tuple[str, str, int, str]:
        """Process a user message and generate AI response.
        Returns (ai_response, style_note, receptivity, phase)."""
        session = self.get_session(session_id)
        if not session or session.status != "active":
            return "会话不存在或已结束", "", 0, ""

        # Add user message
        session.add_message(role="user", content=user_message)

        # Get current phase
        current_phase = self._detect_phase(session)
        growth_context = self.weekly_review_store.build_growth_context(session.user)

        if session.mode == "customer":
            # AI plays customer
            ai_response, receptivity, end_reason = self.role_engine.generate_customer_response(
                conversation=session.conversation,
                scenario=session.scenario,
                growth_context=growth_context,
            )
            session.add_message(role="assistant", content=ai_response)
            session.receptivity_history.append(receptivity)
            style_note = ""

            # Check if customer ended conversation naturally via <end_conversation> tag
            if end_reason:
                session.status = "completed"
                session.ended_at = datetime.now().isoformat()
                session.end_reason = end_reason

            # Check if customer walked away (receptivity = 0)
            elif receptivity <= 0:
                session.status = "completed"
                session.ended_at = datetime.now().isoformat()
                session.end_reason = "离开"

        else:
            # AI plays salesperson
            style_profile = None
            if session.style_profile_id:
                style_profile = self.style_store.load(session.style_profile_id)

            if not style_profile:
                # Fallback: create a default style
                style_profile = StyleProfile(
                    name="专业顾问",
                    description="专业、温和、以客户需求为中心的销售风格",
                    source_file="",
                    extracted_traits={
                        "communication_pattern": "先倾听后表达，善用开放式问题",
                        "tone": "温和专业，不施压",
                        "objection_strategy": "共情认可+重新框架",
                        "closing_style": "渐进式成交",
                        "key_phrases": ["我理解您的顾虑", "从您的角度来看"],
                        "avoid_patterns": ["直接否定客户"],
                        "pacing": "慢节奏，多次确认理解",
                    },
                )

            turn_number = len(session.conversation)
            ai_response, style_note = self.role_engine.generate_sales_response(
                conversation=session.conversation,
                style_profile=style_profile,
                scenario=session.scenario,
                current_phase=current_phase,
                turn_number=turn_number,
                growth_context=growth_context,
            )
            session.add_message(role="assistant", content=ai_response, metadata={"style_note": style_note})
            receptivity = 0

        # Update phase tracking
        session.phases.append({"turn": len(session.conversation), "phase": current_phase})

        # Check max turns
        if len(session.conversation) >= config.MAX_TURNS_PER_SESSION * 2:
            session.status = "completed"
            session.ended_at = datetime.now().isoformat()

        self.session_store.save(session)
        return ai_response, style_note, receptivity, current_phase

    def end_session(self, session_id: str) -> TrainingSession | None:
        """End an active training session."""
        session = self.get_session(session_id)
        if not session:
            return None

        session.status = "completed"
        session.ended_at = datetime.now().isoformat()
        self.session_store.save(session)
        return session

    def _detect_phase(self, session: TrainingSession) -> str:
        """Detect the current conversation phase based on message count."""
        turn_count = len(session.conversation)
        if turn_count <= 2:
            return "开场"
        elif turn_count <= 6:
            return "需求挖掘"
        elif turn_count <= 10:
            return "方案呈现"
        elif turn_count <= 14:
            return "异议处理"
        else:
            return "促成交易"
