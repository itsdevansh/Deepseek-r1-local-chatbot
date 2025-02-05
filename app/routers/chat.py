from fastapi import APIRouter, Depends
from app.utils.jwt import get_current_user
from fastapi.security import OAuth2PasswordBearer
from app.models import chatDict
from outdated.chatbot import get_workflow, run_chatbot
from langchain_core.messages import AIMessage, HumanMessage

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter(prefix="/chat", tags=["chat"])

graph = get_workflow() 
config = {"configurable": {"thread_id": "1"}}

@router.post("/reply", response_model=chatDict)
async def ask_chatbot(user_message: chatDict):
    current_state = graph.get_state(config=config)
    if current_state.values == {}:
        current_state = {
        "messages": [("user", user_message.message)],
    }
    else:
        current_state.values["messages"].append(HumanMessage(user_message.message))
        current_state = current_state.values
    updated_state = run_chatbot(graph, current_state)
    reply = chatDict(message=updated_state.values["messages"][-1].content)
    return reply
