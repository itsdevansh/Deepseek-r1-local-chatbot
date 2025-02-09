// main.js
const dotenv = require("dotenv");
const { DateTime } = require("luxon");
const { ChatOpenAI } = require("@langchain/openai");
const { ChatOllama } = require("@langchain/ollama");
const { createReactAgent } = require("langgraph/prebuilt");
const { MemorySaver } = require("langgraph/checkpoint/memory");
const { StateGraph, START, END, MessagesState } = require("langgraph/graph");
const { AIMessage, HumanMessage } = require("@langchain/core/messages");
const { google } = require("googleapis");
const fs = require("fs").promises;
const path = require("path");

// Import calendar tools
const {
  createEvent,
  getEvents,
  updateEvent,
  deleteEvent,
  initGoogleCalendar,
} = require("./event_handler");

// Constants
const TOKEN_FILE = "token.json";
const CLIENT_SECRET_FILE = "credentials.json";
const SCOPES = ["https://www.googleapis.com/auth/calendar"];

/**
 * Initialize the LLM model
 */
async function initModel() {
  try {
    const MODEL_NAME = process.env.MODEL_NAME;
    const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

    const llm = new ChatOpenAI({
      modelName: MODEL_NAME,
      temperature: 0.3,
      apiKey: OPENAI_API_KEY,
    });

    console.log("Model initialized successfully:", llm);
    return llm;
  } catch (error) {
    console.error(`Model cannot be initialized: ${error}`);
    throw error;
  }
}

/**
 * Calendar agent node implementation
 */
async function calendarAgent(state) {
  try {
    const userMessage = state.messages[state.messages.length - 1].content;
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

    const graphAgent = await createReactAgent(
      llm,
      [createEvent, getEvents, updateEvent, deleteEvent],
      prompt
    );

    const result = await graphAgent.invoke(state);
    console.log(
      "Final state:",
      result.messages[result.messages.length - 1].content
    );

    result.messages[result.messages.length - 1] = new HumanMessage({
      content: result.messages[result.messages.length - 1].content,
      name: "calendar",
    });

    state.messages.push(...result.messages);
    return state;
  } catch (error) {
    console.error(`Error in calendar_agent: ${error}`);
    return state;
  }
}

/**
 * Scheduling agent implementation
 */
async function schedulingAgent(state) {
  try {
    const agentMessage = state.messages[state.messages.length - 1].content;
    const date = DateTime.now().toFormat("dd/MM/yyyy, HH:mm:ss");

    const prompt = `
      You are an intelligent task scheduling that schedules user's tasks or events at reasonable times by analysing user's schedule for the day. You need to think how much time will each task take and what order should to schedule the tasks in.
      Remember that today's date and time ${date}. Schedule events only after the current time without overlap with existing events.
      Your input: ${agentMessage}
      output date/time values in ISO 8601/RFC3339 format including the time zone information.
      Output all user's tasks with the scheduled start time and end time and all other information you received. Respond only in valid json format.
    `;

    const deepseek = new ChatOllama({ model: "deepseek-r1:7b" });
    console.log("----------------------------", deepseek);

    const graphAgent = await createReactAgent(deepseek, [], prompt);
    const result = await graphAgent.invoke(state);
    console.log("Scheduling agent result:", result);

    result.messages[result.messages.length - 1] = new HumanMessage({
      content:
        result.messages[result.messages.length - 1].content.split(
          "</think>"
        )[1],
      name: "calendar",
    });

    state.messages.push(...result.messages);
    return state;
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
  const workflow = new StateGraph(MessagesState);

  workflow.addNode("calendar", calendarAgent);
  workflow.addNode("scheduler", schedulingAgent);
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
  initGoogleCalendar(creds);
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
 * Main execution
 */
async function main() {
  try {
    dotenv.config();
    let creds = null;

    // Handle Google Calendar authentication
    if (
      await fs
        .access(TOKEN_FILE)
        .then(() => true)
        .catch(() => false)
    ) {
      const tokenContent = await fs.readFile(TOKEN_FILE);
      creds = google.auth.fromJSON(JSON.parse(tokenContent));
    }

    if (!creds || !creds.valid) {
      if (creds && creds.expired && creds.refresh_token) {
        await creds.refresh();
      } else {
        const content = await fs.readFile(CLIENT_SECRET_FILE);
        const { client_secret, client_id, redirect_uris } =
          JSON.parse(content).installed;
        const oAuth2Client = new google.auth.OAuth2(
          client_id,
          client_secret,
          redirect_uris[0]
        );

        const authUrl = oAuth2Client.generateAuthUrl({
          access_type: "offline",
          scope: SCOPES,
        });

        console.log("Authorize this app by visiting this url:", authUrl);
        // Handle authorization code input (You might want to implement a proper way to get this)
        // For now, we'll just throw an error
        throw new Error("Need to implement authorization code handling");
      }
    }

    const initialMessage = new HumanMessage({
      content: "List tomorrow's events",
    });

    const state = new MessagesState({
      messages: [initialMessage],
    });

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

// Run the application
if (require.main === module) {
  main().catch(console.error);
}

module.exports = {
  initModel,
  calendarAgent,
  schedulingAgent,
  getWorkflow,
  runChatbot,
};
