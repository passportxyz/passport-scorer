module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/src'],
  testMatch: ['**/*.test.ts'],
  reporters: ['default', '<rootDir>/jest/DBLoggerReporter.js'],
  setupFiles: ['dotenv/config'],
  moduleFileExtensions: ['ts', 'js', 'json', 'node'],
  moduleNameMapper: {
    '^uint8arrays(.*)$': '<rootDir>/node_modules/uint8arrays/dist/src$1',
    '^multiformats(.*)$': '<rootDir>/node_modules/multiformats/dist/src$1',
    '^@ipld/dag-cbor(.*)$': '<rootDir>/node_modules/@ipld/dag-cbor/dist/index.min.js',
  },
  extensionsToTreatAsEsm: ['.ts'],
  transformIgnorePatterns: [],
  transform: {
    'node_modules/.*.js$': 'babel-jest',
    'src/.*.ts$': 'ts-jest',
  },
};
