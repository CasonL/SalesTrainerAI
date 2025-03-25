"""
Claude 3.7 Sonnet Extended API Service

This module provides a unified interface for interacting with the Claude 3.7 Sonnet Extended API
for the Sales Training AI application.
"""
import logging
import time
import os
from typing import List, Dict, Any, Optional
import anthropic

# Configure logging
logger = logging.getLogger(__name__)

# Constants
MODEL_NAME = "claude-3-7-sonnet-20240219"  # Using Claude 3.7 Sonnet Extended
MAX_TOKENS = 4000
DEFAULT_TEMPERATURE = 0.7

class ClaudeService:
    """Service for interacting with Claude 3.7 Sonnet Extended API."""
    
    _instance = None
    
    def __new__(cls, api_key=None):
        """Implement as singleton to ensure consistent client usage."""
        if cls._instance is None:
            cls._instance = super(ClaudeService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, api_key=None):
        """Initialize the Claude API client."""
        if getattr(self, '_initialized', False):
            return
            
        # Get API key from parameter or environment
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("Anthropic API key is required")
        
        # Initialize the Anthropic client
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self._initialized = True
        logger.info("Claude API service initialized")
    
    def generate_response(
        self, 
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = MAX_TOKENS
    ) -> str:
        """
        Generate a response from Claude based on conversation history.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            system_prompt: System prompt for the model
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
        """
        try:
            # Format messages for Anthropic API
            formatted_messages = []
            for msg in messages:
                if msg.get('role') and msg.get('content'):
                    # Map 'assistant' role to 'assistant' for Anthropic
                    role = msg['role']
                    if role == 'assistant':
                        role = 'assistant'
                    formatted_messages.append({
                        "role": role,
                        "content": msg['content']
                    })
            
            # Call the API with retry logic
            max_retries = 3
            backoff_factor = 1.5
            
            for attempt in range(max_retries):
                try:
                    start_time = time.time()
                    response = self.client.messages.create(
                        model=MODEL_NAME,
                        system=system_prompt,
                        messages=formatted_messages,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    duration = time.time() - start_time
                    logger.info(f"Claude API request completed in {duration:.2f}s")
                    
                    # Extract the assistant's response
                    if response and response.content:
                        return response.content[0].text
                    else:
                        logger.warning("Empty response received from Claude API")
                        return ""
                        
                except anthropic.RateLimitError as e:
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor ** attempt
                        logger.warning(f"Rate limit exceeded, retrying in {wait_time}s. Error: {e}")
                        time.sleep(wait_time)
                    else:
                        raise
                except (anthropic.APIError, anthropic.APIConnectionError) as e:
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor ** attempt
                        logger.warning(f"API error, retrying in {wait_time}s. Error: {e}")
                        time.sleep(wait_time)
                    else:
                        raise
            
            # If we get here, all retries failed
            raise RuntimeError("Failed to get response after multiple retries")
                
        except Exception as e:
            logger.error(f"Error generating Claude response: {str(e)}")
            raise
    
    def generate_customer_persona(self, sales_info: Dict[str, Any]) -> str:
        """
        Generate a detailed customer persona based on sales context.
        
        Args:
            sales_info: Dictionary with 'product_service', 'target_market', and 'sales_experience'
            
        Returns:
            Detailed customer persona text
        """
        # Extract the info we need
        product = sales_info.get('product_service', '')
        market = sales_info.get('target_market', '')
        experience = sales_info.get('sales_experience', 'intermediate')
        
        # Create the system prompt for persona generation
        system_prompt = f"""Generate a detailed, realistic customer persona for a sales roleplay scenario. 
This should be for a {'business customer (B2B)' if 'b2b' in market.lower() else 'consumer (B2C)'} sales context.

The customer should be interested in: {product}

Include the following in your persona:
1. Background information (name, age, role, company if B2B)
2. Personality traits and communication style
3. Specific needs and pain points related to the product/service
4. Potential objections they might have
5. Buying motivation and decision factors
6. Make this persona thoughtfully calibrated to a salesperson with {experience} experience level

Create a rich, detailed character that feels like a real person with genuine concerns and interests.
"""
        
        # Send the request to Claude
        messages = []  # No conversation history for persona generation
        return self.generate_response(messages, system_prompt, temperature=0.8)
    
    def generate_roleplay_response(
        self, 
        conversation_history: List[Dict[str, str]], 
        persona: str,
        sales_info: Dict[str, Any]
    ) -> str:
        """
        Generate a roleplay response based on conversation history.
        
        Args:
            conversation_history: List of message dictionaries with 'role' and 'content'
            persona: The customer persona description
            sales_info: Dictionary with sales context information
            
        Returns:
            Generated roleplay response
        """
        # Create the system prompt for the roleplay
        system_prompt = f"""You are roleplaying as a customer with the following persona:

{persona}

Your job is to respond naturally as this customer would, based on the conversation history. 
You should raise appropriate objections and ask questions while being realistic.
The person you're talking to is a salesperson with {sales_info.get('sales_experience', 'some')} experience selling {sales_info.get('product_service', 'their product/service')}.

Guidelines:
- Stay in character as the customer at all times
- Respond conversationally and naturally 
- Express appropriate emotions and hesitations
- Never break character to explain what you're doing
- Be somewhat skeptical but not unreasonably difficult
- Ask questions that a real customer would ask
- Raise realistic objections about price, features, or alternatives
- React to how well the salesperson addresses your needs and concerns
"""
        
        # Send the request to Claude
        return self.generate_response(conversation_history, system_prompt)
    
    def generate_feedback(self, conversation_history: List[Dict[str, str]]) -> str:
        """
        Generate feedback on a sales conversation.
        
        Args:
            conversation_history: List of message dictionaries with 'role' and 'content'
            
        Returns:
            Structured feedback on the sales conversation
        """
        system_prompt = """Analyze this sales roleplay conversation between a salesperson (user) and a customer (assistant).
Provide detailed, constructive feedback with these clearly labeled sections:

### Strengths
Highlight what the salesperson did well, with specific examples from the conversation.

### Areas for Improvement
Identify specific opportunities the salesperson missed or things they could have handled better.

### Actionable Recommendations
Provide 3-5 concrete techniques, phrases, or approaches the salesperson could implement in future conversations.

Be specific, balanced, and focus on practical advice that will help them improve their sales skills.
"""
        
        # Send the request to Claude with lower temperature for more consistent feedback
        return self.generate_response(conversation_history, system_prompt, temperature=0.3)

# Create a singleton instance for import and use elsewhere
claude_service = ClaudeService()
