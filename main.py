import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
import vapi_python as vapi

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Feynman Learning Assistant")

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Specify your frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Vapi client
vapi.api_key = os.environ.get("VAPI_API_KEY")

# Model for conversation input
class ConversationInput(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    user_id: str

# Model for creating a new learning session
class NewSession(BaseModel):
    topic: str
    difficulty_level: str = "beginner"
    user_id: str

# Store active conversations (in production, use a database)
active_conversations = {}

@app.post("/create_assistant")
async def create_assistant(session: NewSession):
    """Create a new Feynman learning assistant for a specific topic"""
    try:
        # Create a new assistant using vapi_python
        assistant = vapi.Assistant.create(
            name=f"Feynman Learning Assistant - {session.topic}",
            model="anthropic/claude-3-opus-20240229",  # Or your preferred model
            instructions=f"""
                You are a Feynman Learning Assistant teaching about {session.topic} at a {session.difficulty_level} level.
                Your goal is to guide the user through the Feynman technique:
                1. Have them explain what they know about the topic
                2. Identify gaps in their understanding
                3. Help them simplify complex concepts
                4. Guide them to teach the concept back to you
                5. Provide feedback on their explanations
                
                Always use simple language and encourage the user to explain concepts in their own words.
            """
        )
        
        # Create a new conversation
        conversation = vapi.Conversation.create(
            assistant_id=assistant.id,
            metadata={"user_id": session.user_id, "topic": session.topic}
        )
        
        # Store the conversation
        active_conversations[conversation.id] = {
            "assistant_id": assistant.id,
            "topic": session.topic,
            "user_id": session.user_id
        }
        
        return {
            "conversation_id": conversation.id,
            "assistant_id": assistant.id,
            "topic": session.topic
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create assistant: {str(e)}")

@app.post("/send_message")
async def send_message(conversation_input: ConversationInput):
    """Send a message to the assistant and get a response"""
    try:
        if not conversation_input.conversation_id:
            raise HTTPException(status_code=400, detail="Conversation ID is required")
        
        if conversation_input.conversation_id not in active_conversations:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Verify user authorization
        if active_conversations[conversation_input.conversation_id]["user_id"] != conversation_input.user_id:
            raise HTTPException(status_code=403, detail="Unauthorized access to conversation")
        
        # Send message to the conversation
        message = vapi.Message.create(
            conversation_id=conversation_input.conversation_id,
            role="user",
            content=conversation_input.message
        )
        
        # Get the assistant's response
        response = vapi.Message.create(
            conversation_id=conversation_input.conversation_id,
            role="assistant"
        )
        
        return {
            "response": response.content,
            "message_id": response.id,
            "conversation_id": conversation_input.conversation_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")

@app.get("/conversations/{user_id}")
async def get_user_conversations(user_id: str):
    """Get all conversations for a specific user"""
    try:
        # For a production app, you should query all conversations and filter by metadata
        user_conversations = {
            conv_id: data for conv_id, data in active_conversations.items() 
            if data["user_id"] == user_id
        }
        
        return {"conversations": user_conversations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conversations: {str(e)}")

@app.delete("/conversation/{conversation_id}")
async def delete_conversation(conversation_id: str, request: Request):
    """Delete a conversation"""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        
        if conversation_id not in active_conversations:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        if active_conversations[conversation_id]["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized access to conversation")
        
        # Delete from Vapi
        vapi.Conversation.delete(conversation_id)
        
        # Remove from local storage
        del active_conversations[conversation_id]
        
        return {"status": "success", "message": "Conversation deleted"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


