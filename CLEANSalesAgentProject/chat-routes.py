"""
Chat routes for the Sales Training AI application.

This module provides routes for the chat interface, conversation management, 
and interaction with the Claude AI service.
"""
from flask import Blueprint, render_template, request, jsonify, g, redirect, url_for
from flask_login import login_required, current_user
from models import db, User, Conversation, Message
from claude_service import claude_service
from datetime import datetime
import json

# Create blueprint
chat = Blueprint('chat', __name__, url_prefix='/chat')

@chat.route('/dashboard')
@login_required
def dashboard():
    """User dashboard page."""
    # Get user's conversations
    conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.updated_at.desc()).limit(5).all()
    
    return render_template('dashboard.html', user=current_user, conversations=conversations)

@chat.route('/')
@login_required
def chat_page():
    """Main chat interface."""
    # Check for conversation ID
    conversation_id = request.args.get('conversation')
    
    if conversation_id:
        # Load existing conversation
        conversation = Conversation.query.filter_by(id=conversation_id, user_id=current_user.id).first_or_404()
    else:
        # Create new conversation
        conversation = Conversation(user_id=current_user.id)
        db.session.add(conversation)
        db.session.commit()
    
    # Get all user conversations for sidebar
    conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.updated_at.desc()).all()
    
    return render_template('chat.html', conversation=conversation, conversations=conversations)

@chat.route('/<int:conversation_id>/message', methods=['POST'])
@login_required
def send_message(conversation_id):
    """Send a message to the AI."""
    # Find conversation
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=current_user.id).first_or_404()
    
    # Get message content
    data = request.get_json()
    message_content = data.get('message', '').strip()
    
    if not message_content:
        return jsonify({'error': 'Message content is required'}), 400
    
    # Create user message
    user_message = Message(
        conversation_id=conversation.id,
        role='user',
        content=message_content
    )
    db.session.add(user_message)
    
    # Generate AI response
    if not conversation.persona:
        # First message needs to collect sales context and generate persona
        ai_response = handle_first_message(conversation, message_content)
    else:
        # Normal message
        ai_response = generate_ai_response(conversation, message_content)
    
    # Create AI message
    ai_message = Message(
        conversation_id=conversation.id,
        role='assistant',
        content=ai_response
    )
    db.session.add(ai_message)
    
    # Update conversation
    conversation.updated_at = datetime.utcnow()
    
    # If this is the first real exchange, update the title
    message_count = Message.query.filter_by(conversation_id=conversation.id).count()
    if message_count <= 2 and not conversation.title or conversation.title == "New Conversation":
        # Create a title from the first few words
        words = message_content.split()
        if len(words) > 2:
            # Use first few words as title
            new_title = " ".join(words[:5])
            if len(new_title) > 30:
                new_title = new_title[:27] + "..."
            conversation.title = new_title
    
    # Save changes
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': {
            'role': 'assistant',
            'content': ai_response,
            'timestamp': ai_message.timestamp.isoformat()
        }
    })

@chat.route('/<int:conversation_id>/feedback')
@login_required
def get_feedback(conversation_id):
    """Get AI feedback on the conversation."""
    # Find conversation
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=current_user.id).first_or_404()
    
    # Get messages
    messages = Message.query.filter_by(conversation_id=conversation.id).order_by(Message.timestamp).all()
    
    if len(messages) < 4:
        return jsonify({'error': 'Not enough conversation history to generate feedback'}), 400
    
    # Format messages for Claude
    formatted_messages = [
        {'role': msg.role, 'content': msg.content} for msg in messages
    ]
    
    # Generate feedback
    feedback = claude_service.generate_feedback(formatted_messages)
    
    # Update user's stats based on feedback
    update_user_stats(current_user, feedback)
    
    # Increment completed roleplays
    current_user.completed_roleplays += 1
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'feedback': feedback
    })

@chat.route('/<int:conversation_id>', methods=['DELETE'])
@login_required
def delete_conversation(conversation_id):
    """Delete a conversation."""
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=current_user.id).first_or_404()
    
    db.session.delete(conversation)
    db.session.commit()
    
    return jsonify({'status': 'success'})

def handle_first_message(conversation, message_content):
    """
    Handle the first message in a conversation to collect context and generate persona.
    """
    # Check if message contains sales experience information
    conversation.sales_experience = extract_sales_experience(message_content)
    
    # Respond with a prompt for more info if needed
    if not conversation.sales_experience:
        return "Thanks for starting a roleplay! To create a realistic scenario, I need to know how long you've been in sales. Could you tell me about your sales experience?"
    
    if not conversation.product_service:
        conversation.product_service = extract_product_service(message_content)
        if not conversation.product_service:
            return f"Thanks! You have {conversation.sales_experience} of sales experience. What product or service will you be selling in this roleplay?"
    
    if not conversation.target_market:
        conversation.target_market = extract_target_market(message_content)
        if not conversation.target_market:
            return f"Great! So you'll be selling {conversation.product_service}. Is your target market B2B (business-to-business), B2C (business-to-consumer), or a mix of both?"
    
    # If we have all the info, generate persona
    sales_info = {
        'product_service': conversation.product_service,
        'target_market': conversation.target_market,
        'sales_experience': conversation.sales_experience
    }
    
    # Generate persona
    persona = claude_service.generate_customer_persona(sales_info)
    conversation.persona = persona
    
    # Start the roleplay
    greeting = "Great! Let's begin the roleplay. I'll act as a potential customer based on the information you've provided. I'll respond as this customer would naturally, with appropriate questions and objections.\n\nHello there! How can I help you today?"
    
    return greeting

def generate_ai_response(conversation, message_content):
    """
    Generate an AI response using the Claude service.
    """
    # Get conversation history
    messages = Message.query.filter_by(conversation_id=conversation.id).order_by(Message.timestamp).all()
    
    # Format messages for Claude (limit to last 20 messages for context)
    formatted_messages = [
        {'role': msg.role, 'content': msg.content} for msg in messages[-20:]
    ]
    
    # Add the new user message
    formatted_messages.append({'role': 'user', 'content': message_content})
    
    # Create sales info context
    sales_info = {
        'product_service': conversation.product_service,
        'target_market': conversation.target_market,
        'sales_experience': conversation.sales_experience
    }
    
    # Generate response
    ai_response = claude_service.generate_roleplay_response(
        formatted_messages, 
        conversation.persona,
        sales_info
    )
    
    return ai_response

def extract_sales_experience(message):
    """Extract sales experience information from message."""
    # Simple extraction logic - can be improved with more sophisticated NLP
    message = message.lower()
    
    # Check for years/months patterns
    if any(term in message for term in ['year', 'years', 'yr', 'yrs']):
        for i in range(1, 31):  # Up to 30 years
            if f"{i} year" in message or f"{i} years" in message or f"{i} yr" in message or f"{i} yrs" in message:
                return f"{i} years"
    
    if any(term in message for term in ['month', 'months', 'mo', 'mos']):
        for i in range(1, 36):  # Up to 36 months
            if f"{i} month" in message or f"{i} months" in message or f"{i} mo" in message or f"{i} mos" in message:
                return f"{i} months"
    
    # Check for experience levels
    if any(term in message for term in ['beginner', 'new', 'novice', 'starting']):
        return "beginner"
    elif any(term in message for term in ['intermediate', 'some experience', 'a few years']):
        return "intermediate"
    elif any(term in message for term in ['experienced', 'expert', 'veteran', 'seasoned', 'senior']):
        return "experienced"
    
    return None

def extract_product_service(message):
    """Extract product or service information from message."""
    # This is a simplified extraction - in real app would use better NLP
    message = message.lower()
    
    # Look for selling indicators
    selling_indicators = [
        'selling', 'offer', 'promote', 'market', 'sell', 'product is', 'service is',
        'i sell', 'we sell', 'i\'m selling', 'we\'re selling'
    ]
    
    for indicator in selling_indicators:
        if indicator in message:
            # Extract what comes after the indicator
            parts = message.split(indicator, 1)
            if len(parts) > 1 and parts[1].strip():
                # Extract up to 50 chars or until end of sentence
                product_text = parts[1].strip()
                end_markers = ['.', '!', '?', ',', '\n']
                for marker in end_markers:
                    if marker in product_text:
                        product_text = product_text.split(marker, 1)[0]
                
                return product_text[:50].strip()
    
    return None

def extract_target_market(message):
    """Extract target market information from message."""
    message = message.lower()
    
    if any(term in message for term in ['b2b', 'business to business', 'businesses', 'companies', 'corporations', 'organizations']):
        return 'B2B'
    
    if any(term in message for term in ['b2c', 'business to consumer', 'consumers', 'individuals', 'people', 'retail']):
        return 'B2C'
    
    if any(term in message for term in ['both', 'mix', 'hybrid', 'b2b and b2c', 'b2c and b2b']):
        return 'mixed'
    
    return None

def update_user_stats(user, feedback):
    """Update user stats based on feedback."""
    try:
        # Extract strengths and areas for improvement
        strengths = []
        weaknesses = []
        
        # Simple string-based extraction - could be improved with better parsing
        if "### Strengths" in feedback:
            strengths_section = feedback.split("### Strengths")[1].split("###")[0]
            strength_items = [s.strip() for s in strengths_section.split("-") if s.strip()]
            strengths = [s[:100] for s in strength_items]
        
        if "### Areas for Improvement" in feedback:
            weaknesses_section = feedback.split("### Areas for Improvement")[1].split("###")[0]
            weakness_items = [w.strip() for w in weaknesses_section.split("-") if w.strip()]
            weaknesses = [w[:100] for w in weakness_items]
        
        # Update skills based on the feedback
        skills = user.skills_dict
        
        # This is a simple algorithm - could be improved with better NLP
        # Increase skills mentioned in strengths
        for strength in strengths:
            if "rapport" in strength.lower():
                skills["rapport_building"] = min(100, skills.get("rapport_building", 0) + 5)
            
            if any(term in strength.lower() for term in ["discovery", "question", "listen", "understanding"]):
                skills["needs_discovery"] = min(100, skills.get("needs_discovery", 0) + 5)
            
            if any(term in strength.lower() for term in ["objection", "concern", "handle", "address"]):
                skills["objection_handling"] = min(100, skills.get("objection_handling", 0) + 5)
            
            if any(term in strength.lower() for term in ["close", "closing", "commitment", "decision"]):
                skills["closing"] = min(100, skills.get("closing", 0) + 5)
            
            if any(term in strength.lower() for term in ["product", "knowledge", "feature", "benefit"]):
                skills["product_knowledge"] = min(100, skills.get("product_knowledge", 0) + 5)
        
        # Slower increase for areas with weaknesses
        for weakness in weaknesses:
            if "rapport" in weakness.lower():
                skills["rapport_building"] = max(1, skills.get("rapport_building", 0) + 2)
            
            if any(term in weakness.lower() for term in ["discovery", "question", "listen", "understanding"]):
                skills["needs_discovery"] = max(1, skills.get("needs_discovery", 0) + 2)
            
            if any(term in weakness.lower() for term in ["objection", "concern", "handle", "address"]):
                skills["objection_handling"] = max(1, skills.get("objection_handling", 0) + 2)
            
            if any(term in weakness.lower() for term in ["close", "closing", "commitment", "decision"]):
                skills["closing"] = max(1, skills.get("closing", 0) + 2)
            
            if any(term in weakness.lower() for term in ["product", "knowledge", "feature", "benefit"]):
                skills["product_knowledge"] = max(1, skills.get("product_knowledge", 0) + 2)
        
        # Update user data
        user.skills_dict = skills
        
        # Update strengths and weaknesses
        current_strengths = user.strengths_list
        current_weaknesses = user.weaknesses_list
        
        # Add new items but avoid duplicates
        for strength in strengths:
            if strength and strength not in current_strengths:
                current_strengths.append(strength)
        
        for weakness in weaknesses:
            if weakness and weakness not in current_weaknesses:
                current_weaknesses.append(weakness)
        
        # Keep only the top items
        user.strengths_list = current_strengths[:10]
        user.weaknesses_list = current_weaknesses[:10]
        
    except Exception as e:
        print(f"Error updating user stats: {e}")
