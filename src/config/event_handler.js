const { google } = require("googleapis");
const path = require("path");
const fs = require("fs").promises;

const SCOPES = ["https://www.googleapis.com/auth/calendar"];

let creds = null;

/**
 * Initialize Google Calendar with credentials
 * @param {Object} credentials - The credentials object
 */
function initGoogleCalendar(credentials) {
  creds = credentials;
  console.log("Calendar initialized successfully");
}

/**
 * Create a Google Calendar event
 * @param {Object} params - Event parameters
 * @param {string} params.summary - The summary of the event
 * @param {string} params.location - The location of the event
 * @param {string} params.description - The description of the event
 * @param {string} params.start_time - The start time of the event
 * @param {string} params.end_time - The end time of the event
 * @param {Array<string>} params.attendees - The list of attendees' emails
 * @returns {Promise<string|null>} The link to the created event or null if error
 */
async function createEvent({
  summary,
  location,
  description,
  start_time,
  end_time,
  attendees,
}) {
  try {
    const calendar = google.calendar({ version: "v3", auth: creds });
    const event = {
      summary,
      location,
      description,
      start: { dateTime: start_time, timeZone: "America/Los_Angeles" },
      end: { dateTime: end_time, timeZone: "America/Los_Angeles" },
      recurrence: ["RRULE:FREQ=DAILY;COUNT=1"],
      attendees: attendees.map((email) => ({ email })),
      reminders: {
        useDefault: false,
        overrides: [
          { method: "email", minutes: 24 * 60 },
          { method: "popup", minutes: 10 },
        ],
      },
    };

    const response = await calendar.events.insert({
      calendarId: "primary",
      requestBody: event,
    });

    console.log("Event created:", response.data.htmlLink);
    return `Event created: ${response.data.htmlLink}`;
  } catch (error) {
    console.error("An error occurred:", error);
    return null;
  }
}

/**
 * Get Google Calendar events for a date range
 * @param {string} startDateTime - The start time (format: 2011-06-03T10:00:00-07:00)
 * @param {string} endDateTime - The end time (format: 2011-06-03T14:00:00-07:00)
 * @returns {Promise<Array<Object>|Object>} List of events or error object
 */
async function getEvents(startDateTime, endDateTime) {
  try {
    const calendar = google.calendar({ version: "v3", auth: creds });
    const response = await calendar.events.list({
      calendarId: "primary",
      timeMin: startDateTime,
      timeMax: endDateTime,
      singleEvents: true,
    });

    return response.data.items.map((event) => ({
      eventId: event.id,
      summary: event.summary,
      start: event.start,
      end: event.end,
    }));
  } catch (error) {
    console.error("An error occurred:", error);
    return { error };
  }
}

/**
 * Update a Google Calendar event
 * @param {Object} params - Event parameters
 * @param {string} params.eventId - The ID of the event to update
 * @param {string} params.summary - The summary of the event
 * @param {string} params.location - The location of the event
 * @param {string} params.description - The description of the event
 * @param {string} params.start_time - The start time of the event
 * @param {string} params.end_time - The end time of the event
 * @param {Array<string>} params.attendees - The list of attendees' emails
 * @returns {Promise<string>} The link to the updated event
 */
async function updateEvent({
  eventId,
  summary,
  location,
  description,
  start_time,
  end_time,
  attendees,
}) {
  try {
    const calendar = google.calendar({ version: "v3", auth: creds });
    const event = await calendar.events.get({
      calendarId: "primary",
      eventId,
    });

    const updatedEvent = {
      ...event.data,
      summary,
      location,
      description,
      start: { dateTime: start_time, timeZone: "America/Los_Angeles" },
      end: { dateTime: end_time, timeZone: "America/Los_Angeles" },
      attendees: attendees.map((email) => ({ email })),
    };

    const response = await calendar.events.update({
      calendarId: "primary",
      eventId,
      requestBody: updatedEvent,
    });

    console.log("Event updated:", response.data.htmlLink);
    return response.data.htmlLink;
  } catch (error) {
    console.error("An error occurred:", error);
    return error;
  }
}

/**
 * Delete a Google Calendar event
 * @param {string} eventId - The ID of the event to delete
 * @returns {Promise<string>} The link to the deleted event
 */
async function deleteEvent(eventId) {
  try {
    const calendar = google.calendar({ version: "v3", auth: creds });
    const event = await calendar.events.get({
      calendarId: "primary",
      eventId,
    });

    await calendar.events.delete({
      calendarId: "primary",
      eventId,
    });

    console.log("Event deleted:", event.data.htmlLink);
    return event.data.htmlLink;
  } catch (error) {
    console.error("An error occurred:", error);
    return error;
  }
}

module.exports = {
  initGoogleCalendar,
  createEvent,
  getEvents,
  updateEvent,
  deleteEvent,
};
