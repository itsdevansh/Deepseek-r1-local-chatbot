// main.js
const dotenv = require("dotenv");
const { DateTime } = require("luxon");
const { ChatOpenAI } = require("@langchain/openai");
const { ChatOllama } = require("@langchain/ollama");
const { createReactAgent } = require("@langchain/langgraph/prebuilt");
const { MemorySaver, Annotation, StateGraph, START, END } = require("@langchain/langgraph");
const { BaseMessage, AIMessage, HumanMessage } = require("@langchain/core/messages");
const { google } = require("googleapis");
const { authenticate } = require('@google-cloud/local-auth');
const fs = require("fs").promises;
const path = require("path");
const User = require('../models/user.model');

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
const CREDENTIALS_PATH = path.join(process.cwd(), 'credentials.json');
const SCOPES = ["https://www.googleapis.com/auth/calendar"];


const GraphAnnotation = Annotation.Root({
  // Define a 'messages' channel to store an array of BaseMessage objects
  messages: Annotation<BaseMessage()>({
    // Reducer function: Combines the current state with new messages
    reducer: (currentState, updateValue) => currentState.concat(updateValue),
    // Default function: Initialize the channel with an empty array
    default: () => [],
  })
});

/**
 * Initialize OpenAI GPT
 */
async function initCalendarAgent(userMessage) {
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
    User input: "${userMessage}"
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
    console.log("Model initialized successfully:", llm);
    const calendarAgent = await createReactAgent(
      llm,
      [createEvent, getEvents, updateEvent, deleteEvent],
      prompt
    );
    return calendarAgent;
  } catch (error) {
    console.error(`Model cannot be initialized: ${error}`);
    throw error;
  }
}

/**
 * Initialize Deepseek
 */
async function initSchedulingAgent(agentMessage) {
  try {
    const date = DateTime.now().toFormat("dd/MM/yyyy, HH:mm:ss");
    const prompt = `
    You are an intelligent task scheduling that schedules user's tasks or events at reasonable times by analysing user's schedule for the day. You need to think how much time will each task take and what order should to schedule the tasks in.
    Remember that today's date and time ${date}. Schedule events only after the current time without overlap with existing events.
    Your input: ${agentMessage}
    output date/time values in ISO 8601/RFC3339 format including the time zone information.
    Output all user's tasks with the scheduled start time and end time and all other information you received. Respond only in valid json format.
  `;

    const deepseek = new ChatOllama({ model: "deepseek-r1:7b" });
    console.log("Model initialized successfully:", deepseek);
    const schedulerAgent = await createReactAgent(deepseek, [], prompt);
    return schedulerAgent;
  } catch (error) {
    console.error(`Model cannot be initialized: ${error}`);
    throw error;
  }
}

/**
 * Calendar agent node implementation
 */
async function calendarNode(state) {
  try {
    const userMessage = state.messages[state.messages.length - 1].content;
    const calendarAgent = initCalendarAgent(userMessage)
    const response = await calendarAgent.invoke(state);

    console.log(
      "Final state:",
      response.messages[response.messages.length - 1].content
    );

    response.messages[response.messages.length - 1] = new HumanMessage({
      content: response.messages[response.messages.length - 1].content,
      name: "calendar",
    });

    return { messages: [response] };
  } catch (error) {
    console.error(`Error in calendar_agent: ${error}`);
    return state;
  }
}

/**
 * Scheduling agent implementation
 */
async function schedulingNode(state) {
  try {
    const agentMessage = state.messages[state.messages.length - 1].content;
    const schedulerAgent = initSchedulingAgent(agentMessage);
    const response = await schedulerAgent.invoke(state);
    console.log("Scheduling agent response:", response);

    response.messages[response.messages.length - 1] = new HumanMessage({
      content:
        response.messages[response.messages.length - 1].content.split(
          "</think>"
        )[1],
      name: "scheduler",
    });

    return { messages: [response] };
  } catch (error) {
    console.error(`Error in scheduling_agent: ${error}`);
    return state;
  }
}

/**
 * Helper function to print streaming output
 */
function printStream(stream) {
  try {
    for (const s of stream) {
      if (typeof s === "object") {
        if ("branch" in s) {
          console.log(`Branch condition met: ${s.branch}`);
        } else if ("agent" in s && "messages" in s.agent) {
          const message = s.agent.messages[s.agent.messages.length - 1];
          if (message instanceof AIMessage) {
            console.log(message.content);
          }
        } else {
          console.log("Other stream output:", s);
        }
      } else {
        console.log("Unexpected stream format:", s);
      }
    }
  } catch (error) {
    console.error(`Error in print_stream: ${error}`);
  }
}

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
  const workflow = new StateGraph(GraphAnnotation);

  workflow.addNode("calendar", calendarNode);
  workflow.addNode("scheduler", schedulingNode);
  workflow.addEdge(START, "calendar");
  workflow.addConditionalEdges("calendar", scheduleDecision);
  workflow.addEdge("scheduler", "calendar");

  const memory = new MemorySaver();
  const graph = await workflow.compile({ checkpointer: memory });
  return graph;
}

/**
 * Main runner function
 */
async function runChatbot(graph, state, creds) {
  await initGoogleCalendar(creds);
  const config = { configurable: { thread_id: "1" } };

  for await (const chunk of graph.stream(state, config)) {
    console.log(
      "--------------------------------------------------------------------"
    );
    console.log(chunk);
  }

  return graph.getState(config);
}

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
    type: 'authorized_user',
    client_id: key.client_id,
    client_secret: key.client_secret,
    refresh_token: client.credentials.refresh_token,
  });
  await User.updateCredByEmail(payload, email)
  // await fs.writeFile(TOKEN_PATH, payload);
}

/**
 * Load or request or authorization to call APIs.
 *
 */
async function authorize(creds, email) {
  try {
    if (creds != "") {
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
  } catch(error) {
    console.error("Error in authenticating google calendar:", error);
  }
}


/**
 * Main execution
 */
async function main() {
  try {
    // Handle Google Calendar authentication
    const creds = authorize()

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
  authorize
};
