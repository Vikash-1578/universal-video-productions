"""The Master Orchestrator with State Regression and Live Progress Reporting."""
from __future__ import annotations
from app.core.pipeline import AgentState, get_next_state
import logging

log = logging.getLogger("app.core.orchestrator")

class Orchestrator:
    def __init__(self, hub): self.hub = hub

    async def run_pipeline(self, project_id: int, initial_input: dict, bot=None, chat_id=None):
        current_state = AgentState.RESEARCHING
        current_input = initial_input
        REGRESSION_MAP = {
            AgentState.VERIFYING_ACCURACY: AgentState.RESEARCHING,
            AgentState.CHECKING_VIRALITY: AgentState.SCRIPTING,
            AgentState.QUALITY_CONTROL: AgentState.SCRIPTING,
            AgentState.CHECKING_MEDIA: AgentState.SOURCING_MEDIA,
            AgentState.VERIFYING_VIDEO: AgentState.EDITING,
        }
        while current_state is not None and current_state != AgentState.COMPLETED:
            if bot and chat_id:
                desc = self.agent_descriptions.get(current_state, f"Processing {current_state.name}...")
                await bot.send_message(chat_id, f"━━━━━━━━━━━━━━━━━━━━━━━━\n{desc}\n⏳ **Status:** In Progress...", parse_mode="Markdown")
            agent = self._get_agent_for_state(current_state)
            if not agent:
                current_state = get_next_state(current_state)
                continue
            try:
                result = await agent.run(project_id, current_input)
                current_input = result
                current_state = get_next_state(current_state)
            except Exception as e:
                fallback = REGRESSION_MAP.get(current_state)
                if fallback:
                    if bot and chat_id:
                        await bot.send_message(chat_id, f"⚠️ **Quality Alert!**\nSending back to {fallback.name} to fix: {e}", parse_mode="Markdown")
                    current_state = fallback
                else:
                    if bot and chat_id: await bot.send_message(chat_id, f"❌ Critical Failure: {e}")
                    return {"status": "failed", "error": str(e)}
        if bot and chat_id: await bot.send_message(chat_id, "🎉 **Mission Accomplished!** Video is ready.", parse_mode="Markdown")
        return {"status": "success", "final_output": current_input}

    def _get_agent_for_state(self, state: AgentState):
        mapping = {
            AgentState.RESEARCHING: self.hub.research_agent, AgentState.VERIFYING_ACCURACY: self.hub.accuracy_agent,
            AgentState.SCRIPTING: self.hub.scripting_agent, AgentState.CHECKING_VIRALITY: self.hub.virality_agent,
            AgentState.QUALITY_CONTROL: self.hub.quality_agent, AgentState.VOICEOVER: self.hub.voice_agent,
            AgentState.SOURCING_MEDIA: self.hub.media_agent, AgentState.CHECKING_MEDIA: self.hub.media_checker_agent,
            AgentState.EDITING: self.hub.editor_agent, AgentState.VERIFYING_VIDEO: self.hub.video_checker_agent,
            AgentState.THUMBNAIL_GEN: self.hub.thumbnail_agent, AgentState.SEO_OPTIMIZATION: self.hub.seo_agent,
            AgentState.ANALYZING: self.hub.analyser_agent, AgentState.CONFIGURING: self.hub.config_agent,
        }
        return mapping.get(state)

    @property
    def agent_descriptions(self):
        return {
            AgentState.RESEARCHING: "🔍 **Agent 1 (Research):** Gathering deep facts...",
            AgentState.VERIFYING_ACCURACY: "🧪 **Agent 2 (Accuracy):** Cross-verifying claims...",
            AgentState.SCRIPTING: "✍️ **Agent 3 (Scripting):** Crafting the Hinglish story...",
            AgentState.CHECKING_VIRALITY: "📈 **Agent 4 (Virality):** Optimizing for retention...",
            AgentState.QUALITY_CONTROL: "🧐 **Agent 5 (Quality):** Checking brand tone...",
            AgentState.VOICEOVER: "🎙️ **Agent 6 (Voice):** Synthesizing human-like audio...",
            AgentState.SOURCING_MEDIA: "🖼️ **Agent 7 (Media):** Sourcing visuals...",
            AgentState.CHECKING_MEDIA: "👁️ **Agent 8 (Media Checker):** Verifying visuals...",
            AgentState.EDITING: "🎬 **Agent 9 (Editor):** Professional assembly...",
            AgentState.VERIFYING_VIDEO: "✅ **Agent 10 (Video Checker):** Final scan...",
            AgentState.THUMBNAIL_GEN: "🎨 **Agent 11 (Thumbnail):** Designing high-CTR art...",
            AgentState.SEO_OPTIMIZATION: "🚀 **Agent 12 (SEO):** Optimizing titles/tags...",
            AgentState.ANALYZING: "📊 **Agent 13 (Analyser):** Studying performance...",
            AgentState.CONFIGURING: "⚙️ **Agent 14 (Config):** Tuning system...",
        }
