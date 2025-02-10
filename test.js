require("dotenv").config();
const {
  MemorySaver,
  Annotation,
  StateGraph,
  START,
  END,
  messagesStateReducer,
} = require("@langchain/langgraph");
const {
  BaseMessage,
  AIMessage,
  HumanMessage,
} = require("@langchain/core/messages");
const { tool } = require("@langchain/core/tools");
const { ChatAnthropic } = require("@langchain/anthropic");
const { ToolNode } = require("@langchain/langgraph/prebuilt");
const { z } = require("zod");
const MODEL_NAME = process.env.MODEL_NAME;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

// Define the graph state
// See here for more info: https://langchain-ai.github.io/langgraphjs/how-tos/define-state/
const StateAnnotation = Annotation.Root({
  messages:
    Annotation <
    [BaseMessage] >
    {
      // `messagesStateReducer` function defines how `messages` state key should be updated
      // (in this case it appends new messages to the list and overwrites messages with the same ID)
      reducer: messagesStateReducer,
    },
});

// Define the tools for the agent to use
const weatherTool = tool(
  async ({ query }) => {
    // This is a placeholder for the actual implementation
    if (
      query.toLowerCase().includes("sf") ||
      query.toLowerCase().includes("san francisco")
    ) {
      return "It's 60 degrees and foggy.";
    }
    return "It's 90 degrees and sunny.";
  },
  {
    name: "weather",
    description: "Call to get the current weather for a location.",
    schema: z.object({
      query: z.string().describe("The query to use in your search."),
    }),
  }
);

const tools = [weatherTool];
const toolNode = new ToolNode(tools);

const model = new ChatAnthropic({
  modelName: MODEL_NAME,
  temperature: 0.3,
  apiKey: OPENAI_API_KEY,
}).bindTools(tools);

// Define the function that determines whether to continue or not
// We can extract the state typing via `StateAnnotation.State`
function shouldContinue(state) {
  const messages = state.messages;
  const lastMessage = messages[messages.length - 1];

  // If the LLM makes a tool call, then we route to the "tools" node
  if (lastMessage.tool_calls?.length) {
    return "tools";
  }
  // Otherwise, we stop (reply to the user)
  return "__end__";
}

// Define the function that calls the model
async function callModel(state) {
  const messages = state.messages;
  const response = await model.invoke(messages);

  // We return a list, because this will get added to the existing list
  return { messages: [response] };
}

// Define a new graph
const workflow = new StateGraph(StateAnnotation)
  .addNode("agent", callModel)
  .addNode("tools", toolNode)
  .addEdge("__start__", "agent")
  .addConditionalEdges("agent", shouldContinue)
  .addEdge("tools", "agent");

// Initialize memory to persist state between graph runs
const checkpointer = new MemorySaver();

// Finally, we compile it!
// This compiles it into a LangChain Runnable.
// Note that we're (optionally) passing the memory when compiling the graph
const app = workflow.compile({ checkpointer });

// Use the Runnable
async function run() {
  const finalState = await app.invoke(
    { messages: [new HumanMessage("what is the weather in sf")] },
    { configurable: { thread_id: "42" } }
  );
  console.log(finalState);
  console.log(finalState.messages[finalState.messages.length - 1].content);
}


