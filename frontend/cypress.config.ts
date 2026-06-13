import { defineConfig } from "cypress";

export default defineConfig({
  projectId: '24bw4t',
  allowCypressEnv: false,
  e2e: {
    baseUrl: "http://localhost:8501",
    supportFile: false,
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
  },
});