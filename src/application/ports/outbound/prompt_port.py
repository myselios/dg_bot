"""
PromptPort - Interface for prompt management operations.

This port defines the contract for AI prompt template management.
Adapters implementing this interface handle prompt loading, versioning, and rendering.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

from src.domain.value_objects.prompt_version import PromptType, PromptVersion


class PromptPort(ABC):
    """
    Port interface for prompt management.

    This interface defines operations for managing AI prompt templates,
    including version control, rendering, and validation.
    """

    @abstractmethod
    async def get_prompt(
        self,
        prompt_type: PromptType,
        version: Optional[str] = None,
    ) -> str:
        """
        Get raw prompt template.

        Args:
            prompt_type: Type of prompt (entry/exit/general)
            version: Specific version to retrieve (default: current)

        Returns:
            Raw prompt template string

        Raises:
            PromptNotFoundError: If prompt version not found
        """
        pass

    @abstractmethod
    async def get_current_version(self, prompt_type: PromptType) -> PromptVersion:
        """
        Get current (latest) version for a prompt type.

        Args:
            prompt_type: Type of prompt

        Returns:
            PromptVersion with current version info
        """
        pass

    @abstractmethod
    async def render_prompt(
        self,
        prompt_type: PromptType,
        context: Dict[str, Any],
        version: Optional[str] = None,
    ) -> str:
        """
        Render prompt template with context.

        Args:
            prompt_type: Type of prompt
            context: Context data for template rendering
            version: Specific version to use (default: current)

        Returns:
            Rendered prompt string ready for AI

        Raises:
            PromptRenderError: If rendering fails
        """
        pass

    @abstractmethod
    async def list_versions(self, prompt_type: PromptType) -> List[str]:
        """
        List all available versions for a prompt type.

        Args:
            prompt_type: Type of prompt

        Returns:
            List of version strings (e.g., ["v1.0.0", "v2.0.0"])
        """
        pass

    @abstractmethod
    async def validate_prompt(self, prompt: str) -> bool:
        """
        Validate a prompt string.

        Args:
            prompt: Prompt string to validate

        Returns:
            True if prompt is valid
        """
        pass
