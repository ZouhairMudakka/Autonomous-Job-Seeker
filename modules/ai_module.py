"""
AI Module for handling chat interactions and LLM integration.
Uses the universal model selector for LLM interactions.
"""

from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime
from utils.universal_model import ModelSelector

class AIModule:
    # Chat UX Settings
    DEFAULT_CHAT_SETTINGS = {
        "auto_scroll": True,
        "show_timestamps": True,
        "show_typing_indicator": True,
        "message_grouping": True,  # Group consecutive messages from same sender
        "max_message_length": 2000,
        "typing_speed": 50,  # Characters per second for typing animation
        "theme": "light",
        "font_size": "medium",
        "enable_code_highlighting": True,
        "enable_markdown": True,
        "enable_emoji_suggestions": True,
        "show_message_status": True,  # Sent, Delivered, Read, etc.
        "notification_sound": True,
        "enable_quick_replies": True
    }

    # Quick Reply Templates
    QUICK_REPLIES = {
        "job_search": [
            "Tell me about my job search progress",
            "What jobs match my profile?",
            "How can I improve my CV?",
            "Show me my application statistics"
        ],
        "automation": [
            "Start job search automation",
            "Pause the automation",
            "Change search criteria",
            "Update my preferences"
        ],
        "help": [
            "How does this work?",
            "What features are available?",
            "Show me a tutorial",
            "Report an issue"
        ]
    }

    # Message Categories
    MESSAGE_CATEGORIES = {
        "COMMAND": {"icon": "⌘", "color": "#4CAF50"},
        "QUESTION": {"icon": "❓", "color": "#2196F3"},
        "STATUS": {"icon": "ℹ️", "color": "#9E9E9E"},
        "ERROR": {"icon": "⚠️", "color": "#F44336"},
        "SUCCESS": {"icon": "✅", "color": "#4CAF50"},
        "FEEDBACK": {"icon": "📝", "color": "#FF9800"}
    }

    def __init__(self, model_name: str = None, **kwargs):
        """Initialize the AI module with specified model."""
        self.model_selector = ModelSelector()
        # Use the default model from ModelSelector if none specified
        self.model_name = model_name or self.model_selector.DEFAULT_TEXT_MODEL
        self.config = kwargs
        self.last_interaction = None
        self.conversation_history = []
        
        # Initialize chat settings with defaults
        self.chat_settings = self.DEFAULT_CHAT_SETTINGS.copy()
        self.chat_settings.update(kwargs.get('chat_settings', {}))
        
        # Initialize UX state
        self.typing_indicator_visible = False
        self.unread_messages = 0
        self.active_quick_replies = []
        self.suggested_responses = []
        self.pinned_messages = []
        self.message_reactions = {}  # Message ID -> List of reactions
        
    def update_chat_settings(self, settings: Dict[str, Any]):
        """Update chat UX settings."""
        self.chat_settings.update(settings)
        
    def get_chat_settings(self) -> Dict[str, Any]:
        """Get current chat UX settings."""
        return self.chat_settings.copy()
        
    def get_quick_replies(self, category: str = None) -> List[str]:
        """Get quick reply suggestions for a category."""
        if category and category in self.QUICK_REPLIES:
            return self.QUICK_REPLIES[category]
        return sum(self.QUICK_REPLIES.values(), [])
        
    def categorize_message(self, message: str) -> str:
        """Categorize a message based on its content."""
        message = message.lower()
        if message.startswith(("/", "!", "?")):
            return "COMMAND"
        elif "?" in message:
            return "QUESTION"
        elif any(word in message for word in ["help", "how", "what", "why", "when"]):
            return "QUESTION"
        elif any(word in message for word in ["error", "issue", "problem", "fail"]):
            return "ERROR"
        elif any(word in message for word in ["thanks", "good", "great", "awesome"]):
            return "FEEDBACK"
        return "STATUS"
        
    def format_message_for_display(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Format a message for display in the GUI."""
        formatted = message.copy()
        
        # Add message category and styling
        category = self.categorize_message(message["content"])
        formatted["category"] = category
        formatted["icon"] = self.MESSAGE_CATEGORIES[category]["icon"]
        formatted["color"] = self.MESSAGE_CATEGORIES[category]["color"]
        
        # Format timestamp if enabled
        if self.chat_settings["show_timestamps"]:
            timestamp = message.get("timestamp")
            if timestamp:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)
                formatted["display_time"] = timestamp.strftime("%H:%M:%S")
        
        # Add message status if enabled
        if self.chat_settings["show_message_status"]:
            formatted["status"] = message.get("status", "sent")
            
        # Format code blocks if enabled
        if self.chat_settings["enable_code_highlighting"]:
            content = formatted["content"]
            # Simple code block detection and formatting
            if "```" in content:
                parts = content.split("```")
                for i in range(1, len(parts), 2):
                    if i < len(parts):
                        parts[i] = f'<code class="highlight">{parts[i]}</code>'
                formatted["content"] = "".join(parts)
                
        return formatted
        
    def get_suggested_responses(self, message: str) -> List[str]:
        """Get suggested responses based on the current message."""
        category = self.categorize_message(message)
        if category == "QUESTION":
            return self.QUICK_REPLIES["help"]
        elif category == "COMMAND":
            return self.QUICK_REPLIES["automation"]
        return self.QUICK_REPLIES["job_search"]
        
    def pin_message(self, message_id: str):
        """Pin a message for quick reference."""
        if message_id not in self.pinned_messages:
            self.pinned_messages.append(message_id)
            
    def unpin_message(self, message_id: str):
        """Unpin a message."""
        if message_id in self.pinned_messages:
            self.pinned_messages.remove(message_id)
            
    def add_reaction(self, message_id: str, reaction: str):
        """Add a reaction to a message."""
        if message_id not in self.message_reactions:
            self.message_reactions[message_id] = []
        if reaction not in self.message_reactions[message_id]:
            self.message_reactions[message_id].append(reaction)
            
    def remove_reaction(self, message_id: str, reaction: str):
        """Remove a reaction from a message."""
        if message_id in self.message_reactions:
            if reaction in self.message_reactions[message_id]:
                self.message_reactions[message_id].remove(reaction)
                
    def get_message_reactions(self, message_id: str) -> List[str]:
        """Get all reactions for a message."""
        return self.message_reactions.get(message_id, [])

    def get_model_info(self) -> str:
        """Get information about the current AI model."""
        token_limits = self.model_selector.get_token_limits(self.model_name)
        vision_support = "Supports vision" if self.model_selector.supports_vision(self.model_name) else "No vision support"
        return f"{self.model_name} ({vision_support}, Input: {token_limits['input']}, Output: {token_limits['output']} tokens)"
        
    async def process_message(self, message: str) -> str:
        """Process a user message and generate a response using the universal model."""
        try:
            self.last_interaction = datetime.now()
            message_id = f"msg_{int(datetime.now().timestamp())}"
            
            # Validate message length
            if len(message) > self.chat_settings["max_message_length"]:
                raise ValueError(f"Message exceeds maximum length of {self.chat_settings['max_message_length']} characters")
            
            # Add message to conversation history with UX metadata
            user_message = {
                "id": message_id,
                "role": "user",
                "content": message,
                "timestamp": self.last_interaction,
                "status": "sent",
                "category": self.categorize_message(message)
            }
            
            self.conversation_history.append(user_message)
            
            # Get suggested responses for quick replies
            self.suggested_responses = self.get_suggested_responses(message)
            
            # Format messages for the model
            formatted_messages = self._format_messages_for_model()
            
            # Get response from the model
            response = self.model_selector.chat_completion(
                messages=formatted_messages,
                model=self.model_name,
                **self.config
            )
            
            # Add response to conversation history with UX metadata
            response_id = f"msg_{int(datetime.now().timestamp())}"
            assistant_message = {
                "id": response_id,
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now(),
                "status": "delivered",
                "category": self.categorize_message(response)
            }
            
            self.conversation_history.append(assistant_message)
            
            # Update UX state
            self.unread_messages += 1
            
            # Keep only last 50 messages
            if len(self.conversation_history) > 50:
                self.conversation_history = self.conversation_history[-50:]
                
            return response
            
        except Exception as e:
            error_id = f"msg_{int(datetime.now().timestamp())}"
            error_message = {
                "id": error_id,
                "role": "system",
                "content": str(e),
                "timestamp": datetime.now(),
                "status": "error",
                "category": "ERROR"
            }
            self.conversation_history.append(error_message)
            raise Exception(f"Error processing message: {str(e)}")
    
    def _format_messages_for_model(self) -> List[Dict[str, str]]:
        """Format conversation history for the model."""
        system_message = {
            "role": "system",
            "content": "You are a helpful AI assistant integrated into a job search automation system. "
                      "You can help users with their job search, provide advice, and answer questions "
                      "about the automation process."
        }
        
        # Convert conversation history to model format
        messages = [system_message]
        for msg in self.conversation_history[-10:]:  # Only use last 10 messages
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
            
        return messages
            
    def get_conversation_history(self) -> list:
        """Get the conversation history."""
        return self.conversation_history
        
    def clear_conversation_history(self):
        """Clear the conversation history."""
        self.conversation_history = []
        
    async def get_completion(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """
        Get a completion from the AI model using the universal model.
        This is a separate method for non-chat completions.
        """
        try:
            messages = [{
                "role": "user",
                "content": prompt
            }]
            
            return self.model_selector.chat_completion(
                messages=messages,
                model=self.model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                **self.config
            )
        except Exception as e:
            raise Exception(f"Error getting completion: {str(e)}")
            
    def change_model(self, new_model: str):
        """Change the active model."""
        if new_model in self.model_selector.OPENAI_MODELS + \
           self.model_selector.DEEPSEEK_MODELS + \
           self.model_selector.MODEL_BOX_MODELS:
            self.model_name = new_model
        else:
            raise ValueError(f"Unsupported model: {new_model}")
            
    def get_available_models(self) -> Dict[str, List[str]]:
        """Get all available models grouped by provider."""
        return {
            "OpenAI": self.model_selector.OPENAI_MODELS,
            "DeepSeek": self.model_selector.DEEPSEEK_MODELS,
            "ModelBox": self.model_selector.MODEL_BOX_MODELS
        }

    async def process_message_stream(self, message: str, chunk_callback=None) -> str:
        """Process a user message and generate a streaming response."""
        try:
            self.last_interaction = datetime.now()
            message_id = f"msg_{int(datetime.now().timestamp())}"
            
            # Validate message length
            if len(message) > self.chat_settings["max_message_length"]:
                raise ValueError(f"Message exceeds maximum length of {self.chat_settings['max_message_length']} characters")
            
            # Add message to conversation history with UX metadata
            user_message = {
                "id": message_id,
                "role": "user",
                "content": message,
                "timestamp": self.last_interaction,
                "status": "sent",
                "category": self.categorize_message(message)
            }
            
            self.conversation_history.append(user_message)
            
            # Get suggested responses for quick replies
            self.suggested_responses = self.get_suggested_responses(message)
            
            # Format messages for the model
            formatted_messages = self._format_messages_for_model()
            
            # Show typing indicator if enabled
            if self.chat_settings["show_typing_indicator"]:
                self.typing_indicator_visible = True
                if chunk_callback:
                    await chunk_callback("typing_start")
            
            # Get streaming response from the model
            response = await self.model_selector.stream_chat_response(
                messages=formatted_messages,
                model=self.model_name,
                chunk_callback=self._create_streaming_callback(chunk_callback),
                **self.config
            )
            
            # Hide typing indicator
            if self.chat_settings["show_typing_indicator"]:
                self.typing_indicator_visible = False
                if chunk_callback:
                    await chunk_callback("typing_end")
            
            # Add complete response to conversation history with UX metadata
            response_id = f"msg_{int(datetime.now().timestamp())}"
            assistant_message = {
                "id": response_id,
                "role": "assistant",
                "content": response["content"],
                "timestamp": datetime.now(),
                "status": "delivered",
                "category": self.categorize_message(response["content"]),
                "metadata": response["metadata"]
            }
            
            self.conversation_history.append(assistant_message)
            
            # Update UX state
            self.unread_messages += 1
            
            # Keep only last 50 messages
            if len(self.conversation_history) > 50:
                self.conversation_history = self.conversation_history[-50:]
                
            return response["content"]
            
        except Exception as e:
            error_id = f"msg_{int(datetime.now().timestamp())}"
            error_message = {
                "id": error_id,
                "role": "system",
                "content": str(e),
                "timestamp": datetime.now(),
                "status": "error",
                "category": "ERROR"
            }
            self.conversation_history.append(error_message)
            
            # Hide typing indicator on error
            if self.chat_settings["show_typing_indicator"]:
                self.typing_indicator_visible = False
                if chunk_callback:
                    await chunk_callback("typing_end")
                    
            raise Exception(f"Error processing message stream: {str(e)}")

    def _create_streaming_callback(self, original_callback):
        """Create a callback that handles streaming chunks with UX features."""
        async def enhanced_callback(chunk):
            if not chunk:
                return
                
            # Apply typing animation if enabled
            if self.chat_settings["typing_speed"] > 0:
                chunk_length = len(chunk)
                delay = chunk_length / self.chat_settings["typing_speed"]
                await asyncio.sleep(delay)
            
            # Format code blocks if enabled
            if self.chat_settings["enable_code_highlighting"] and "```" in chunk:
                chunk = self._format_code_block(chunk)
            
            # Call original callback with enhanced chunk
            if original_callback:
                await original_callback(chunk)
                
        return enhanced_callback

    def _format_code_block(self, text: str) -> str:
        """Format code blocks with syntax highlighting."""
        if not self.chat_settings["enable_code_highlighting"]:
            return text
            
        if "```" not in text:
            return text
            
        parts = text.split("```")
        for i in range(1, len(parts), 2):
            if i < len(parts):
                parts[i] = f'<code class="highlight">{parts[i]}</code>'
        return "".join(parts)

    def mark_messages_as_read(self):
        """Mark all messages as read."""
        self.unread_messages = 0
        for msg in self.conversation_history:
            if msg["status"] == "delivered":
                msg["status"] = "read"

    def export_conversation(self, format: str = "txt") -> bytes:
        """Export the conversation history in the specified format."""
        try:
            return self.model_selector.export_chat_history(self.conversation_history, format)
        except Exception as e:
            raise Exception(f"Error exporting conversation: {str(e)}")

    def get_supported_export_formats(self) -> List[str]:
        """Get list of supported export formats."""
        return ["txt", "json", "markdown", "html"]

    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get statistics about the conversation."""
        try:
            total_messages = len(self.conversation_history)
            user_messages = sum(1 for msg in self.conversation_history if msg["role"] == "user")
            ai_messages = sum(1 for msg in self.conversation_history if msg["role"] == "assistant")
            
            # Calculate average response time if metadata is available
            response_times = []
            for i in range(1, len(self.conversation_history)):
                if (self.conversation_history[i]["role"] == "assistant" and 
                    "metadata" in self.conversation_history[i]):
                    metadata = self.conversation_history[i]["metadata"]
                    if "response_time" in metadata:
                        response_times.append(metadata["response_time"])
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else None
            
            # Get token usage if available
            total_tokens = 0
            for msg in self.conversation_history:
                if "metadata" in msg and "token_count" in msg["metadata"]:
                    total_tokens += msg["metadata"]["token_count"]
            
            return {
                "total_messages": total_messages,
                "user_messages": user_messages,
                "ai_messages": ai_messages,
                "avg_response_time": avg_response_time,
                "total_tokens": total_tokens if total_tokens > 0 else None,
                "start_time": self.conversation_history[0]["timestamp"] if self.conversation_history else None,
                "last_interaction": self.last_interaction,
                "current_model": self.model_name
            }
        except Exception as e:
            raise Exception(f"Error getting conversation stats: {str(e)}") 