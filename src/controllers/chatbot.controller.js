// main.js
require("dotenv").config();
const { DateTime } = require("luxon");
const { ChatOpenAI } = require("@langchain/openai");
const { ChatOllama } = require("@langchain/ollama");
const { createReactAgent } = require("@langchain/langgraph/prebuilt");
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
  map,
} = require("@langchain/core/messages");
const { google } = require("googleapis");
const { authenticate } = require("@google-cloud/local-auth");
const fs = require("fs").promises;
const path = require("path");
const User = require("../models/user.model");

// Import calendar tools
const {
  createEvent,
  getEvents,
  updateEvent,
  deleteEvent,
  initGoogleCalendar,
} = require("../config/event_handler");

// Constants
// const TOKEN_PATH = path.join(process.cwd(), 'token.json');
const CREDENTIALS_PATH = path.join(process.cwd(), "credentials.json");
const SCOPES = ["https://www.googleapis.com/auth/calendar"];

// const GraphAnnotation = Annotation.Root({
//   // Define a 'messages' channel to store an array of BaseMessage objects
//   messages:
//     Annotation <
//     [BaseMessage] >
//     {
//       // Reducer function: Combines the current state with new messages
//       reducer: messagesStateReducer,
//     },
// });

const MessageFormat = {
  channels: {
    messages: {
      value: [BaseMessage],
      reducer: messagesStateReducer,
    },
  },
};

/**
 * Initialize OpenAI GPT
 */
async function initCalendarAgent() {
  try {
    const MODEL_NAME = process.env.MODEL_NAME;
    const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
    const todayStr = DateTime.now().toFormat("yyyy-MM-dd");
    const prompt = `
    You are an intelligent assistant that manages a Google Calendar using tools you are provided.
    You can call only one tool at a time, once you create one event you have to call again if you want to create another event.
    While updating or deleting events, get all the events for the mentioned date from 12am to 11:59pm. Use the id of that particular event to perform the necessary action.
    output date/time values in ISO 8601/RFC3339 format including the time zone information.
    If the user has provided a to-do list. Your task is to:
     1. Parse the following to-do list input and extract each task.
     2. Fetch the events of the mentioned day using get_event tool as prescribed from 12am to 11:59pm.
     3. If you do not have times for each task set the boolean needs_deep_analysis as True for scheduling tasks and return the output in the mentioned format. There exists an agent that will provide you with the times for each events. You can create events only after that.
     4. If you do have times, set the boolean needs_deep_analysis as False and move to the next step.
     5. For each scheduled task, call the tool "create_event" with these parameters:
     - summary: the task description.
     - location: an empty string if not provided.
     - description: "Scheduled from to-do list".
     - start_time: the scheduled start time.
     - end_time: the scheduled end time.
     - attendees: an empty list.
    Today's date is ${todayStr}.
    Output must only be a valid JSON in the following format with no extra characters:
     - message: Message for the agent.
     - needs_deep_analysis: Boolean indicating need for deeper scheduling help if the user asks to schedule a task or gives a todo list.
     - scheduling_context: Additional metadata with user input.
     - response_for_user: Response to the user for user input with all information (if any) formatted in a pretty way if needs_deep_analysis is False, else empty.
  `;
    const llm = new ChatOpenAI({
      modelName: MODEL_NAME,
      temperature: 0.3,
      apiKey: OPENAI_API_KEY,
    });
    const calendarAgent = createReactAgent({
      llm: llm,
      tools: [createEvent, getEvents, updateEvent, deleteEvent],
      stateModifier: prompt,
    });
    return calendarAgent;
  } catch (error) {
    console.error(`Model cannot be initialized: ${error}`);
    throw error;
  }
}

/**
 * Initialize Deepseek
 */
async function initSchedulingAgent() {
  try {
    const date = DateTime.now().toFormat("dd/MM/yyyy, HH:mm:ss");
    const prompt = `
    You are an intelligent task scheduling that schedules user's tasks or events at reasonable times by analysing user's schedule for the day. You need to think how much time will each task take and what order should to schedule the tasks in.
    Remember that today's date and time ${date}. Schedule events only after the current time without overlap with existing events.
    output date/time values in ISO 8601/RFC3339 format including the time zone information.
    Output all user's tasks with the scheduled start time and end time and all other information you received. Respond only in valid json format.
  `;

    const deepseek = new ChatOllama({ model: "deepseek-r1:7b" });
    console.log("Model initialized successfully:", deepseek);
    const schedulerAgent = createReactAgent({
      llm: deepseek,
      tools: [],
      stateModifier: prompt,
    });
    return schedulerAgent;
  } catch (error) {
    console.error(`Model cannot be initialized: ${error}`);
    throw error;
  }
}

/**
 * Calendar agent node implementation
 */
const calendarNode = async (state) => {
  try {
    const calendarAgent = await initCalendarAgent();

    var response = await calendarAgent.invoke({ messages: state.messages });

    // response = response.messages.map(convertToLangChainMessage);

    // response.messages[response.messages.length - 1] = new HumanMessage({
    //   content: response.messages[response.messages.length - 1].content,
    //   name: "calendar",
    // });

    return { messages: response.messages };
  } catch (error) {
    console.error(`Error in calendar_agent: ${error}`);
    throw error;
  }
};

/**
 * Scheduling agent implementation
 */
const schedulingNode = async (state) => {
  try {
    const schedulerAgent = await initSchedulingAgent();

    const response = await schedulerAgent.invoke({
      messages: state.messages,
    });

    // response.messages[response.messages.length - 1] = new HumanMessage({
    //   content:
    //     response.messages[response.messages.length - 1].content.split(
    //       "</think>"
    //     )[1],
    //   name: "scheduler",
    // });

    return { messages: response.messages };
  } catch (error) {
    console.error(`Error in scheduling_agent: ${error}`);
    throw error;
  }
};

/**
 * Schedule decision function
 */
function scheduleDecision(state) {
  if (
    JSON.parse(state.messages[state.messages.length - 1].content)
      .needs_deep_analysis
  ) {
    return "scheduler";
  }
  return END;
}

/**
 * Get workflow function
 */
async function getWorkflow() {
  try {
    const workflow = new StateGraph({ channels: MessageFormat.channels })
      .addNode("calendar", calendarNode)
      .addNode("scheduler", schedulingNode)
      .addEdge(START, "calendar")
      .addConditionalEdges("calendar", scheduleDecision)
      .addEdge("scheduler", "calendar");

    const checkpointer = new MemorySaver();
    const graph = workflow.compile({ checkpointer });
    return graph;
  } catch (error) {
    console.log(`Error in getWorkflow: ${error.message}`);
    throw error;
  }
}

/**
 * Main runner function
 */
const runChatbot = async (state, creds) => {
  try {
    await initGoogleCalendar(creds);
    const workflow = new StateGraph({ channels: MessageFormat.channels })
      .addNode("calendar", calendarNode)
      .addNode("scheduler", schedulingNode)
      .addEdge(START, "calendar")
      .addConditionalEdges("calendar", scheduleDecision)
      .addEdge("scheduler", "calendar");

    const config = { configurable: { thread_id: "42" } };
    const checkpointer = new MemorySaver();
    const graph = workflow.compile({ checkpointer });

    for await (
      const chunk of await graph.stream(state, config, {
        streamMode: "values",
      })
    ) {
      console.log(chunk["messages"]);
      console.log("\n====\n");
    }
    // await graph.invoke(state, config);
    return graph.getState(config);
  } catch (error) {
    console.error(`Error in runChatbot: ${error.message}`);
    throw error;
  }
};

/**
 * Serializes credentials to a file compatible with GoogleAuth.fromJSON.
 *
 * @param {OAuth2Client} client
 * @return {Promise<void>}
 */
async function saveCredentials(client, email) {
  const content = await fs.readFile(CREDENTIALS_PATH);
  const keys = JSON.parse(content);
  const key = keys.installed || keys.web;
  const payload = JSON.stringify({
    type: "authorized_user",
    client_id: key.client_id,
    client_secret: key.client_secret,
    refresh_token: client.credentials.refresh_token,
  });
  await User.updateCredByEmail(payload, email);
}

/**
 * Load or request or authorization to call APIs.
 *
 */
async function authorize(creds, email) {
  try {
    if (creds != null) {
      const credentials = JSON.parse(creds);
      return google.auth.fromJSON(credentials);
    }
    client = await authenticate({
      scopes: SCOPES,
      keyfilePath: CREDENTIALS_PATH,
    });
    if (client.credentials) {
      await saveCredentials(client, email);
    }
    return client;
  } catch (error) {
    console.error("Error in authenticating google calendar:", error.message);
    throw error;
  }
}

/**
 * Main execution
 */
async function main() {
  try {
    // Handle Google Calendar authentication
    const creds = authorize();

    const initialMessage = new HumanMessage({
      content: "List tomorrow's events",
    });

    const state = {
      messages: [initialMessage],
    };

    const workflowGraph = await getWorkflow();
    const finalState = await runChatbot(workflowGraph, state, creds);
    console.log(
      "Final state:",
      finalState.values.messages[finalState.values.messages.length - 1].content
    );
  } catch (error) {
    console.error("Error in main:", error);
  }
}

module.exports = {
  getWorkflow,
  runChatbot,
  authorize,
};
