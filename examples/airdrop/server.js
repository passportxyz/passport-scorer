const { createServer } = require("http");
const { parse } = require("url");
const next = require("next");
const { initializeDatabase } = require("./dbInit"); // Import the initializeDatabase function

const dev = process.env.NODE_ENV !== "production";
const hostname = "localhost";
const port = 3000;
const app = next({ dev, hostname, port });
const handle = app.getRequestHandler();

(async () => {
  // Call the initializeDatabase function
  await initializeDatabase();

  // Start the Next.js server
  app.prepare().then(() => {
    createServer((req, res) => {
      const parsedUrl = parse(req.url, true);
      handle(req, res, parsedUrl);
    }).listen(port, (err) => {
      if (err) throw err;
      console.log(`> Ready on http://${hostname}:${port}`);
    });
  });
})();
