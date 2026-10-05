# FitLab: Use weather for the event

Status: Draft — under review.
Named team approver: Nadia.

## Purpose

Make outfit suggestions appropriate for the weather where and when the user plans to wear them.

## User experience

The user selects an event date and time. The app requests browser location access to determine the current location and retrieves weather relevant to the selected event time.

Users can override their current location with the event's city. City entry also provides a fallback if location access is unavailable or declined. Display the location and time used so the user can check them.

Users do not enter expected weather manually. If a forecast is unavailable, including dates outside the forecast window or weather-service failures, outfit generation continues using the occasion, styling preferences, and other user requirements without weather guidance. The app clearly labels the results as generated without weather guidance.

## Success criteria

- Weather lookup uses the selected event date and time, interpreted in the event location's time zone.
- Users can override the detected location; weather lookup, outfit generation, and critique then use the chosen event location.
- Available weather conditions inform outfit generation and critique.
- The app displays the location, event time, and weather used.
- If a forecast is unavailable for the selected date or a lookup fails, the app clearly states this rather than presenting current conditions as the event forecast.
- There is no manual weather-entry fallback.
- Unavailable forecasts and failed weather lookups do not block outfit generation.
- When weather is unavailable, generation and critique omit weather suitability judgments and scores rather than inventing conditions.

## Open decisions

- Choose a weather provider and supported forecast window during design.
