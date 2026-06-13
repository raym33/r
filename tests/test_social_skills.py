"""Tests for Social Media and Auto-Responder skills."""

import pytest


class TestSocialMediaSkill:
    """Tests for SocialMediaSkill."""

    def test_skill_loads(self):
        """Test skill can be instantiated."""
        from r_cli.skills.social_skill import SocialMediaSkill

        skill = SocialMediaSkill(None)
        assert skill.name == "social"

    def test_has_correct_tools(self):
        """Test skill has expected tools."""
        from r_cli.skills.social_skill import SocialMediaSkill

        skill = SocialMediaSkill(None)
        tools = skill.get_tools()
        tool_names = [t.name for t in tools]

        expected_tools = [
            "social_config",
            "social_connect",
            "social_inbox",
            "social_mentions",
            "social_comments",
            "social_reply",
            "social_post",
            "social_dm",
            "social_queue_add",
            "social_queue_list",
            "social_queue_send",
            "social_stats",
        ]

        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"

    def test_platforms_defined(self):
        """Test all platforms are defined."""
        from r_cli.skills.social_skill import SocialMediaSkill

        skill = SocialMediaSkill(None)

        expected_platforms = ["twitter", "instagram", "facebook", "linkedin", "discord", "telegram"]

        for platform in expected_platforms:
            assert platform in skill.PLATFORMS

    def test_show_config_no_connections(self):
        """Test config shows no connections when none configured."""
        from r_cli.skills.social_skill import SocialMediaSkill

        skill = SocialMediaSkill(None)

        result = skill.show_config()
        assert "Social Media Configuration" in result
        assert "Not connected" in result or "not configured" in result.lower()

    def test_connect_platform_instructions(self):
        """Test connect platform shows instructions."""
        from r_cli.skills.social_skill import SocialMediaSkill

        skill = SocialMediaSkill(None)

        result = skill.connect_platform("twitter")
        assert "Twitter" in result or "environment variable" in result.lower()

    def test_queue_operations(self):
        """Test queue add/list/send operations."""
        from r_cli.skills.social_skill import SocialMediaSkill

        skill = SocialMediaSkill(None)

        # Add to queue
        result = skill.queue_add(
            platform="twitter",
            message_id="123",
            response="Test response",
            priority="high",
        )
        assert "queue" in result.lower()

        # List queue
        result = skill.queue_list()
        assert "123" in result or "Queue" in result

    def test_execute_method(self):
        """Test direct execute method."""
        from r_cli.skills.social_skill import SocialMediaSkill

        skill = SocialMediaSkill(None)

        result = skill.execute(action="config")
        assert "Social Media Configuration" in result


class TestAutoResponderSkill:
    """Tests for AutoResponderSkill."""

    def test_skill_loads(self):
        """Test skill can be instantiated."""
        from r_cli.skills.autoresponder_skill import AutoResponderSkill

        skill = AutoResponderSkill(None)
        assert skill.name == "autoresponder"

    def test_has_correct_tools(self):
        """Test skill has expected tools."""
        from r_cli.skills.autoresponder_skill import AutoResponderSkill

        skill = AutoResponderSkill(None)
        tools = skill.get_tools()
        tool_names = [t.name for t in tools]

        expected_tools = [
            "autoresponder_load_pdf",
            "autoresponder_load_text",
            "autoresponder_kb_status",
            "autoresponder_kb_search",
            "autoresponder_config",
            "autoresponder_add_rule",
            "autoresponder_list_rules",
            "autoresponder_generate",
            "autoresponder_batch",
            "autoresponder_feedback",
            "autoresponder_history",
        ]

        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"

    def test_response_styles(self):
        """Test response styles are defined."""
        from r_cli.skills.autoresponder_skill import AutoResponderSkill

        skill = AutoResponderSkill(None)

        expected_styles = ["professional", "friendly", "casual", "support", "sales"]

        for style in expected_styles:
            assert style in skill.RESPONSE_STYLES

    def test_configure_style(self):
        """Test configuring response style."""
        from r_cli.skills.autoresponder_skill import AutoResponderSkill

        skill = AutoResponderSkill(None)

        result = skill.configure(style="friendly")
        assert "friendly" in result.lower() or "Configuration" in result

    def test_add_rule(self):
        """Test adding response rules."""
        from r_cli.skills.autoresponder_skill import AutoResponderSkill

        skill = AutoResponderSkill(None)

        result = skill.add_rule("Never discuss competitors", priority="must")
        assert "Rule added" in result

        result = skill.list_rules()
        assert "Never discuss competitors" in result

    def test_kb_status_no_rag(self):
        """Test KB status when RAG not available."""
        from r_cli.skills.autoresponder_skill import AutoResponderSkill

        skill = AutoResponderSkill(None)

        result = skill.kb_status()
        # Should either show status or indicate RAG not available
        assert "Knowledge Base" in result or "RAG" in result

    def test_load_text(self):
        """Test loading text into knowledge base."""
        from r_cli.skills.autoresponder_skill import AutoResponderSkill

        skill = AutoResponderSkill(None)

        result = skill.load_text(
            content="This is test content for the knowledge base.",
            title="Test FAQ",
            category="faq",
        )
        # Should either succeed or indicate RAG not available
        assert "added" in result.lower() or "rag" in result.lower() or "error" in result.lower()

    def test_view_history_empty(self):
        """Test viewing empty history."""
        from r_cli.skills.autoresponder_skill import AutoResponderSkill

        skill = AutoResponderSkill(None)

        result = skill.view_history()
        assert "history" in result.lower() or "No response" in result

    def test_execute_method(self):
        """Test direct execute method."""
        from r_cli.skills.autoresponder_skill import AutoResponderSkill

        skill = AutoResponderSkill(None)

        result = skill.execute(action="status")
        assert "Knowledge Base" in result or "RAG" in result


class TestSkillIntegration:
    """Integration tests for social media skills."""

    def test_skills_in_registry(self):
        """Test skills are registered correctly."""
        from r_cli.skills import get_all_skills

        skills = get_all_skills()
        skill_names = [s.name for s in [skill_class(None) for skill_class in skills]]

        assert "social" in skill_names
        assert "autoresponder" in skill_names

    def test_skills_count_increased(self):
        """Test total skill count includes new skills."""
        from r_cli.skills import get_all_skills

        skills = get_all_skills()
        # Should be 75+ skills now (73 + 2 new)
        assert len(skills) >= 75

    def test_tool_parameters_valid(self):
        """Test all tools have valid parameter schemas."""
        from r_cli.skills.autoresponder_skill import AutoResponderSkill
        from r_cli.skills.social_skill import SocialMediaSkill

        for skill_class in [SocialMediaSkill, AutoResponderSkill]:
            skill = skill_class(None)
            for tool in skill.get_tools():
                assert tool.name, "Tool must have a name"
                assert tool.description, "Tool must have a description"
                assert tool.handler, "Tool must have a handler"
                assert "type" in tool.parameters, "Tool parameters must have type"
