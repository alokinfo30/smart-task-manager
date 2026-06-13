const nextJest = require('next/jest')

// Providing path to your Next.js app to load next.config.js and .env files
const createJestConfig = nextJest({
  dir: './',
})

// Custom config to be passed to Jest
const customJestConfig = {
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testEnvironment: 'jest-environment-jsdom',
}

// createJestConfig is exported this way to ensure that next/jest can load the Next.js config which is async
module.exports = createJestConfig(customJestConfig)