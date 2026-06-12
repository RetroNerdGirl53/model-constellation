"""Permission rules module.

Provides rule-based permissions with pattern matching, tool name-based rules,
and category-based rules.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern

logger = logging.getLogger(__name__)


class RuleType(Enum):
    """Types of permission rules.

    Attributes:
        TOOL_NAME: Match by exact tool name.
        TOOL_PATTERN: Match by tool name pattern (regex).
        CATEGORY: Match by tool category.
        PARAMETER: Match by parameter value.
        COMPOSITE: Combine multiple rules.
    """

    TOOL_NAME = "tool_name"
    TOOL_PATTERN = "tool_pattern"
    CATEGORY = "category"
    PARAMETER = "parameter"
    COMPOSITE = "composite"


class RuleAction(Enum):
    """Action to take when a rule matches.

    Attributes:
        ALLOW: Allow the tool execution.
        DENY: Deny the tool execution.
        ASK: Ask for permission (defer to prompt).
    """

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class PermissionRule:
    """A permission rule definition.

    Attributes:
        name: Human-readable rule name.
        rule_type: Type of rule matching.
        pattern: Pattern to match against.
        action: Action to take when matched.
        description: Human-readable description.
        priority: Rule priority (higher = checked first).
        enabled: Whether the rule is active.
    """

    name: str
    rule_type: RuleType
    pattern: str
    action: RuleAction
    description: str = ""
    priority: int = 0
    enabled: bool = True

    def matches(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        category: str = "general",
    ) -> bool:
        """Check if this rule matches the given tool execution.

        Args:
            tool_name: Name of the tool.
            parameters: Tool parameters.
            category: Tool category.

        Returns:
            True if the rule matches, False otherwise.
        """
        if not self.enabled:
            return False

        try:
            if self.rule_type == RuleType.TOOL_NAME:
                return tool_name == self.pattern

            elif self.rule_type == RuleType.TOOL_PATTERN:
                return bool(re.search(self.pattern, tool_name))

            elif self.rule_type == RuleType.CATEGORY:
                return category == self.pattern

            elif self.rule_type == RuleType.PARAMETER:
                return self._match_parameter(parameters)

            elif self.rule_type == RuleType.COMPOSITE:
                return False

            return False

        except re.error as e:
            logger.error(f"Invalid regex pattern '{self.pattern}': {e}")
            return False

    def _match_parameter(self, parameters: Dict[str, Any]) -> bool:
        """Check if parameter rule matches.

        Args:
            parameters: Tool parameters.

        Returns:
            True if parameter matches.
        """
        try:
            key, value_pattern = self.pattern.split(":", 1)
            param_value = parameters.get(key, "")

            if param_value is None:
                return False

            return bool(re.search(value_pattern, str(param_value)))

        except (ValueError, re.error):
            return False


@dataclass
class CompositeRule:
    """A composite rule combining multiple rules.

    Attributes:
        name: Human-readable rule name.
        rules: List of rules to combine.
        operator: How to combine rules ("all" = AND, "any" = OR).
        action: Action to take when matched.
        description: Human-readable description.
        priority: Rule priority.
        enabled: Whether the rule is active.
    """

    name: str
    rules: List[PermissionRule]
    operator: str = "any"
    action: RuleAction = RuleAction.ASK
    description: str = ""
    priority: int = 0
    enabled: bool = True

    def matches(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        category: str = "general",
    ) -> bool:
        """Check if this composite rule matches.

        Args:
            tool_name: Name of the tool.
            parameters: Tool parameters.
            category: Tool category.

        Returns:
            True if the rule matches.
        """
        if not self.enabled:
            return False

        if not self.rules:
            return False

        if self.operator == "all":
            return all(rule.matches(tool_name, parameters, category) for rule in self.rules)
        else:
            return any(rule.matches(tool_name, parameters, category) for rule in self.rules)


class PermissionRuleManager:
    """Manages permission rules and evaluates them.

    Provides rule-based permission checking with support for
    tool name patterns, categories, and parameter matching.
    """

    def __init__(self):
        """Initialize the permission rule manager."""
        self._rules: List[PermissionRule] = []
        self._composite_rules: List[CompositeRule] = []
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """Load default permission rules."""
        default_rules = [
            PermissionRule(
                name="Deny Dangerous Commands",
                rule_type=RuleType.TOOL_NAME,
                pattern="bash",
                action=RuleAction.ASK,
                description="Always ask for bash commands",
                priority=100,
            ),
            PermissionRule(
                name="Deny Network Write",
                rule_type=RuleType.CATEGORY,
                pattern="network",
                action=RuleAction.ASK,
                description="Ask for network operations",
                priority=90,
            ),
            PermissionRule(
                name="Allow Safe Read",
                rule_type=RuleType.TOOL_NAME,
                pattern="read",
                action=RuleAction.ALLOW,
                description="Allow reading files",
                priority=50,
            ),
            PermissionRule(
                name="Allow Safe Glob",
                rule_type=RuleType.TOOL_NAME,
                pattern="glob",
                action=RuleAction.ALLOW,
                description="Allow file globbing",
                priority=50,
            ),
            PermissionRule(
                name="Allow Safe Grep",
                rule_type=RuleType.TOOL_NAME,
                pattern="grep",
                action=RuleAction.ALLOW,
                description="Allow grep search",
                priority=50,
            ),
            PermissionRule(
                name="Deny Parameter Danger",
                rule_type=RuleType.PARAMETER,
                pattern="command:rm\\s+-rf",
                action=RuleAction.DENY,
                description="Deny recursive force remove",
                priority=200,
            ),
            PermissionRule(
                name="Deny Format Command",
                rule_type=RuleType.PARAMETER,
                pattern="command:format\\s+",
                action=RuleAction.DENY,
                description="Deny format commands",
                priority=200,
            ),
            PermissionRule(
                name="Deny Sudo",
                rule_type=RuleType.PARAMETER,
                pattern="command:^sudo\\s+",
                action=RuleAction.ASK,
                description="Ask for sudo commands",
                priority=150,
            ),
            PermissionRule(
                name="Deny Pipe to Shell",
                rule_type=RuleType.PARAMETER,
                pattern="command:.*\\|\\s*sh",
                action=RuleAction.DENY,
                description="Deny piping to shell",
                priority=200,
            ),
        ]

        for rule in default_rules:
            self.add_rule(rule)

    def add_rule(self, rule: PermissionRule) -> None:
        """Add a permission rule.

        Args:
            rule: The rule to add.
        """
        self._rules.append(rule)
        self._rules.sort(key=lambda r: -r.priority)
        logger.debug(f"Added permission rule: {rule.name}")

    def add_composite_rule(self, rule: CompositeRule) -> None:
        """Add a composite rule.

        Args:
            rule: The composite rule to add.
        """
        self._composite_rules.append(rule)
        self._composite_rules.sort(key=lambda r: -r.priority)
        logger.debug(f"Added composite rule: {rule.name}")

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name.

        Args:
            name: Name of the rule to remove.

        Returns:
            True if rule was removed, False if not found.
        """
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                self._rules.pop(i)
                logger.debug(f"Removed permission rule: {name}")
                return True
        return False

    def get_rule(self, name: str) -> Optional[PermissionRule]:
        """Get a rule by name.

        Args:
            name: Name of the rule.

        Returns:
            The rule if found, None otherwise.
        """
        for rule in self._rules:
            if rule.name == name:
                return rule
        return None

    def list_rules(self) -> List[Dict[str, Any]]:
        """List all rules.

        Returns:
            List of rule dictionaries.
        """
        rules_data = []
        for rule in self._rules:
            rules_data.append(
                {
                    "name": rule.name,
                    "type": rule.rule_type.value,
                    "pattern": rule.pattern,
                    "action": rule.action.value,
                    "description": rule.description,
                    "priority": rule.priority,
                    "enabled": rule.enabled,
                }
            )
        return rules_data

    def evaluate(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        category: str = "general",
    ) -> Optional[RuleAction]:
        """Evaluate rules for a tool execution.

        Args:
            tool_name: Name of the tool.
            parameters: Tool parameters.
            category: Tool category.

        Returns:
            RuleAction if a rule matches, None if no rule applies.
        """
        for rule in self._composite_rules:
            if rule.enabled and rule.matches(tool_name, parameters, category):
                logger.debug(f"Composite rule '{rule.name}' matched for {tool_name}")
                return rule.action

        for rule in self._rules:
            if rule.matches(tool_name, parameters, category):
                logger.debug(f"Rule '{rule.name}' matched for {tool_name}")
                return rule.action

        return None

    def check_permission(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        category: str = "general",
    ) -> bool:
        """Check if tool execution is allowed based on rules.

        Args:
            tool_name: Name of the tool.
            parameters: Tool parameters.
            category: Tool category.

        Returns:
            True if allowed, False if denied or no rule applies.
        """
        action = self.evaluate(tool_name, parameters, category)

        if action is None:
            return True

        return action == RuleAction.ALLOW

    def should_prompt(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        category: str = "general",
    ) -> bool:
        """Check if user should be prompted based on rules.

        Args:
            tool_name: Name of the tool.
            parameters: Tool parameters.
            category: Tool category.

        Returns:
            True if user should be prompted.
        """
        action = self.evaluate(tool_name, parameters, category)

        if action is None:
            return True

        return action == RuleAction.ASK

    def clear_rules(self) -> None:
        """Clear all rules."""
        self._rules.clear()
        self._composite_rules.clear()
        logger.info("Cleared all permission rules")

    def create_tool_name_rule(
        self,
        name: str,
        tool_name: str,
        action: RuleAction,
        description: str = "",
        priority: int = 0,
    ) -> PermissionRule:
        """Create a tool name-based rule.

        Args:
            name: Rule name.
            tool_name: Tool name to match.
            action: Action to take.
            description: Description.
            priority: Priority.

        Returns:
            The created rule.
        """
        return PermissionRule(
            name=name,
            rule_type=RuleType.TOOL_NAME,
            pattern=tool_name,
            action=action,
            description=description,
            priority=priority,
        )

    def create_pattern_rule(
        self,
        name: str,
        pattern: str,
        action: RuleAction,
        description: str = "",
        priority: int = 0,
    ) -> PermissionRule:
        """Create a tool pattern-based rule.

        Args:
            name: Rule name.
            pattern: Regex pattern to match.
            action: Action to take.
            description: Description.
            priority: Priority.

        Returns:
            The created rule.
        """
        return PermissionRule(
            name=name,
            rule_type=RuleType.TOOL_PATTERN,
            pattern=pattern,
            action=action,
            description=description,
            priority=priority,
        )

    def create_category_rule(
        self,
        name: str,
        category: str,
        action: RuleAction,
        description: str = "",
        priority: int = 0,
    ) -> PermissionRule:
        """Create a category-based rule.

        Args:
            name: Rule name.
            category: Category to match.
            action: Action to take.
            description: Description.
            priority: Priority.

        Returns:
            The created rule.
        """
        return PermissionRule(
            name=name,
            rule_type=RuleType.CATEGORY,
            pattern=category,
            action=action,
            description=description,
            priority=priority,
        )

    def create_parameter_rule(
        self,
        name: str,
        parameter_key: str,
        value_pattern: str,
        action: RuleAction,
        description: str = "",
        priority: int = 0,
    ) -> PermissionRule:
        """Create a parameter-based rule.

        Args:
            name: Rule name.
            parameter_key: Parameter key to match.
            value_pattern: Regex pattern for parameter value.
            action: Action to take.
            description: Description.
            priority: Priority.

        Returns:
            The created rule.
        """
        return PermissionRule(
            name=name,
            rule_type=RuleType.PARAMETER,
            pattern=f"{parameter_key}:{value_pattern}",
            action=action,
            description=description,
            priority=priority,
        )

    def create_composite_rule(
        self,
        name: str,
        rules: List[PermissionRule],
        operator: str = "any",
        action: RuleAction = RuleAction.ASK,
        description: str = "",
        priority: int = 0,
    ) -> CompositeRule:
        """Create a composite rule.

        Args:
            name: Rule name.
            rules: List of rules to combine.
            operator: How to combine ("all" or "any").
            action: Action to take.
            description: Description.
            priority: Priority.

        Returns:
            The created composite rule.
        """
        return CompositeRule(
            name=name,
            rules=rules,
            operator=operator,
            action=action,
            description=description,
            priority=priority,
        )
