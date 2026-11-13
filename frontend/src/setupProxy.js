const { createProxyMiddleware } = require("http-proxy-middleware");

// Metadata OAuth/MCP (ChatGPT) di root domain diteruskan ke backend.
module.exports = function (app) {
  app.use(createProxyMiddleware("/.well-known", { target: "http://localhost:8001", changeOrigin: false, xfwd: true, logLevel: "warn" }));
};
