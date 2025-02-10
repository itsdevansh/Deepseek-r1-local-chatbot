// src/routes/auth.routes.js
const express = require("express");
const router = express.Router();
const passport = require("passport");
const chatbotController = require("../controllers/chatbot.controller");
const authMiddleware = require("../middleware/auth.middleware");
const { AIMessage, HumanMessage } = require("@langchain/core/messages");
const { google } = require("googleapis");

router.put("/authenticate", authMiddleware, async (req, res) => {
  try {
    const client = chatbotController.authorize(req.user.creds, req.user.email);
    if (client) {
      res
        .status(200)
        .json({ message: "Successfully authenticated to Google Calendar" });
    }
  } catch (error) {
    res.status(500).json({ message: error });
  }
});

router.post("/message", authMiddleware, async (req, res) => {
  if (req.user.creds != "") {
    try {
      const { state, message } = req.body;

      if (state & (state == {})) {
        state = { messages: [new HumanMessage(message)] };
      } else {
        state = {};
        state.messages.append(new HumanMessage(message));
      }
      const graph = await chatbotController.getWorkflow();

      state = await chatbotController.runChatbot(
        graph,
        state,
        google.auth.fromJSON(JSON.parse(req.user.creds))
      );
      const response = JSON.parse(
        state.values.messages[finalState.values.messages.length - 1].content
      )["response_for_user"];
      res.status(200).json({ message: response, state: state });
    } catch (error) {
      res.status(500).json({ message: error });
    }
  } else {
    res.status(401).json({ message: "Not authenticated to Google Calendar" });
  }
});

module.exports = router;
