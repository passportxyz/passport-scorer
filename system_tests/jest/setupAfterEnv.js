jest.retryTimes(4);

// This adds a custom matcher which checks for a status and prints
// response details if it fails. This avoids super unhelpful
// error messages like "expected 500 to be 200"
expect.extend({
  toHaveStatus(received, expectedCode) {
    const { status } = received;
    const pass = expectedCode === status;

    let message = `expected status \x1b[31m${status}\x1b[0m to match \x1b[32m${expectedCode}\x1b[0m.`;
    if (pass) {
      return {
        message: () => message,
        pass: true,
      };
    } else {
      try {
        message += `\n\n\x1b[93mRequest:\n\n${JSON.stringify(received.requestOptions, null, 2)}\x1b[0m`;
      } catch {
        message += ` \x1b[31mUnable to parse request.\x1b[0m`;
      }
      try {
        message += `\n\n\x1b[93mResponse:\n\n${JSON.stringify(received.data, null, 2)}\x1b[0m`;
      } catch {
        message += ` \x1b[31mUnable to parse response.\x1b[0m`;
      }
      return {
        message: () => message,
        pass: false,
      };
    }
  },
});

// Keep track of request cancel tokens globally
global.axiosCancelTokens = [];

// Add cleanup after all tests run
afterAll(() => {
  // Cancel any pending requests
  if (global.axiosCancelTokens && global.axiosCancelTokens.length > 0) {
    console.log(`Cleaning up ${global.axiosCancelTokens.length} pending Axios requests`);
    global.axiosCancelTokens.forEach((token) => {
      try {
        token.cancel("Jest test completed");
      } catch (e) {
        console.log("Error cancelling request:", e);
        // Ignore errors from already completed requests
      }
    });
    global.axiosCancelTokens = [];
  }
});
